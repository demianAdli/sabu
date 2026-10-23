"""
Sabu project
jug_sim_buildings package
geojson_geometry module
Preserve reader geometry and report verified footprint exclusions.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from copy import deepcopy
from math import fsum, isfinite

from hub.city_model_structure.building import Building
from hub.imports.geometry.geojson import Geojson
from hub.imports.geometry_factory import GeometryFactory


class BuildingGeojson(Geojson):
    """Keep multipart footprints and holes in one building.

    The pinned reader's MultiPolygon hole stitching differs from its Polygon
    implementation and can change the footprint area. Reuse the Polygon path
    for each part, then combine the resulting surfaces without rewriting input
    coordinates or making separate city objects.
    """

    @property
    def city(self):
        # Observe actual parsed buildings; do not recalculate area from GeoJSON
        # or infer the reason merely because an ID disappeared.
        if self._city is None:
            self._parsed_buildings = {}
        city = super().city
        retained = {str(building.name) for building in city.buildings}
        self.reader_exclusions = []
        for name, building in self._parsed_buildings.items():
            area = float(building.floor_area)
            if name not in retained and isfinite(area) and 0 <= area < 25:
                self.reader_exclusions.append({
                    'reader_name': name, 'reason_code': 'reader_floor_area_below_minimum',
                    'field': 'geometry', 'reason': 'Reader floor area is below its existing 25 m2 minimum.',
                    'reader_floor_area_m2': area, 'minimum_floor_area_m2': 25.0})
        return city

    def _remember_building(self, building):
        if hasattr(self, '_parsed_buildings'):
            self._parsed_buildings[str(building.name)] = building
        return building

    def _parse_polygon(
        self, coordinates, building_name, building_aliases,
        function, year_of_construction, extrusion_height,
    ):
        # Ring roles come from position, independently of their input winding.
        # The pinned reader instead infers roles from winding, so orient its
        # working copy before delegating. No points or ordinate values change.
        oriented = deepcopy(coordinates)
        for index, ring in enumerate(oriented):
            if len(ring) < 3 or any(len(point) < 2 for point in ring):
                # Keep existing reader handling for incomplete/degenerate input.
                continue
            origin_x, origin_y = ring[0][:2]
            signed_area = fsum(
                (first[0] - origin_x) * (second[1] - origin_y)
                - (second[0] - origin_x) * (first[1] - origin_y)
                for first, second in zip(ring, ring[1:] + ring[:1])
            )
            if (index == 0 and signed_area < 0) or (index > 0 and signed_area > 0):
                ring.reverse()
        return self._remember_building(super()._parse_polygon(
            oriented, building_name, building_aliases,
            function, year_of_construction, extrusion_height,
        ))

    def _parse_multi_polygon(
        self, polygons_coordinates, building_name, building_aliases,
        function, year_of_construction, extrusion_height,
    ):
        parts = [
            self._parse_polygon(
                coordinates, building_name, building_aliases,
                function, year_of_construction, extrusion_height,
            )
            for coordinates in polygons_coordinates
        ]
        building = Building(
            str(building_name),
            [surface for part in parts for surface in part.surfaces],
            year_of_construction,
            function,
        )
        for alias in building_aliases:
            building.add_alias(alias)
        if extrusion_height != 0:
            building.volume = sum(part.volume for part in parts)
        # Replace any per-part observation with the combined building, including
        # all parts and holes, before applying the reader's existing threshold.
        return self._remember_building(building)


class BuildingGeometryFactory(GeometryFactory):
    """Retain the factory interface while adapting its GeoJSON reader."""

    @property
    def _geojson(self):
        reader = BuildingGeojson(
            self._path,
            self._aliases_field,
            self._height_field,
            self._year_of_construction_field,
            self._function_field,
            self._function_to_hub,
            self._hub_crs,
        )
        city = reader.city
        self.reader_exclusions = reader.reader_exclusions
        return city
