"""
Sabu project
jug_sim_buildings package
reprojection module
Adapt the consumed CityGISOO reprojection method without duplicating transforms.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""

from copy import deepcopy
import gc
import importlib.metadata
import inspect
import json
import math
import os
from pathlib import Path

from sabu_chassis.logging import get_logger

from .run_artifacts import file_digest


logger = get_logger(__name__)
TARGET_CRS = 'EPSG:4326'


def check_capability():
    """Check the package actually imported, not the same-version repository copy."""
    try:
        from citygisoo import ScrubLayer
        method = getattr(ScrubLayer, 'reproject_layer', None)
        if not callable(method) or not {
                'target_crs', 'output_path', 'transform_context', 'source_fid_field'
        } <= set(inspect.signature(method).parameters):
            raise RuntimeError('ScrubLayer.reproject_layer has a missing/incompatible signature.')
        source = Path(inspect.getsourcefile(method)).resolve()
        return {'package': 'citygisoo', 'version': importlib.metadata.version('citygisoo'),
                'method': 'ScrubLayer.reproject_layer', 'source_file': str(source),
                **file_digest(source)}
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        raise RuntimeError('Preparation requires the separately maintained CityGISOO '
                           'reproject_layer method in a configured QGIS environment.') from exc


def geometry_structure(geometry):
    coordinates = geometry['coordinates']
    polygons = [coordinates] if geometry['type'] == 'Polygon' else coordinates
    return (geometry['type'], tuple(tuple(tuple(len(point) for point in ring)
                                         for ring in polygon) for polygon in polygons))


def verify_final(features, original_features, *, equivalent=False):
    """Verify identity, attributes and geometry structure after the final serialization."""
    expected = {f['id']: f for f in original_features}
    if len(expected) != len(original_features) or len(features) != len(expected):
        raise ValueError('Final export count/identity mismatch.')
    seen = set()
    for feature in features:
        identifier = feature.get('id')
        if type(identifier) is not int or identifier not in expected or identifier in seen:
            raise ValueError('Final export changed/duplicated prepared IDs.')
        seen.add(identifier)
        original = expected[identifier]
        if feature['properties'] != original['properties']:
            raise ValueError('Final export changed attributes or metrics.')
        geometry = feature['geometry']
        if geometry_structure(geometry) != geometry_structure(original['geometry']):
            raise ValueError('Final export changed geometry type, parts, rings, or positions.')
        polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
        for polygon in polygons:
            for ring in polygon:
                if ring[0] != ring[-1]:
                    raise ValueError('Final export opened a ring.')
                for point in ring:
                    if not all(math.isfinite(v) for v in point) or not (
                            -180 <= point[0] <= 180 and -90 <= point[1] <= 90):
                        raise ValueError('Invalid EPSG:4326 longitude/latitude coordinates.')
        # Geographic reprojection does not change vertical/measure ordinates.
        def positions(g):
            parts = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
            return [point for part in parts for ring in part for point in ring]
        for before, after in zip(positions(original['geometry']), positions(geometry)):
            if before[2:] != after[2:]:
                raise ValueError('Final export changed Z/M ordinates.')
        if equivalent and geometry != original['geometry']:
            raise ValueError('Already-WGS84 export unnecessarily changed coordinates.')


class CityGISOOReprojector:
    def __init__(self):
        self.capability = check_capability()
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from qgis.core import QgsApplication
        self.application = None
        if QgsApplication.instance() is None:
            prefix = os.getenv('JUG_GIS_CITIES_QGIS_PATH') or os.getenv('QGIS_PREFIX_PATH')
            if prefix:
                QgsApplication.setPrefixPath(prefix, True)
            self.application = QgsApplication([], False)
            self.application.initQgis()

    def close(self):
        if self.application is not None:
            self.application.exitQgis()
            self.application = None

    def resolve_crs(self, declarations, config):
        from qgis.core import QgsCoordinateReferenceSystem, Qgis
        def parse(value):
            crs = QgsCoordinateReferenceSystem(value)
            if not crs.isValid():
                crs.createFromOgcWmsCrs(value)
            return crs

        resolved = []
        for origin, value in declarations:
            if value is None:
                continue
            if isinstance(value, dict):
                if value.get('type') != 'name':
                    raise ValueError(f'Unsupported/ambiguous CRS declaration at {origin}.')
                value = value.get('properties', {}).get('name')
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'Invalid source CRS at {origin}.')
            crs = parse(value)
            if not crs.isValid():
                raise ValueError(f'Invalid source CRS at {origin}: {value}.')
            resolved.append((origin, crs))
        if config.preparation_source_crs is not None:
            override = parse(config.preparation_source_crs)
            if not override.isValid():
                raise ValueError('Invalid verified source CRS override.')
            resolved.append(('verified_override', override))
        if not resolved:
            raise ValueError('Source CRS is missing; no CRS may be inferred from coordinates.')
        source = resolved[0][1]
        if any(crs != source for _, crs in resolved):
            raise ValueError('Source CRS declarations/override disagree.')
        measurement = parse(config.preparation_measurement_crs)
        if not measurement.isValid() or measurement.isGeographic() or measurement.mapUnits() != Qgis.DistanceUnit.Meters:
            raise ValueError('Measurement CRS must be a valid projected CRS in metres.')
        return {'source_crs': source.authid() or source.toWkt(), 'target_crs': TARGET_CRS,
                'evidence': [origin for origin, _ in resolved],
                'override_evidence': config.preparation_source_crs_evidence,
                'measurement_crs': measurement.authid() or measurement.toWkt(),
                'status': 'copied' if source == QgsCoordinateReferenceSystem(TARGET_CRS) else 'transformed',
                'capability': self.capability,
                'warnings': ['Source CRS is validated from declarations and lineage, not coordinate guessing.']}

    def geometry_error(self, geometry):
        from osgeo import ogr
        layer_geometry = ogr.CreateGeometryFromJson(json.dumps(geometry))
        if layer_geometry is None or layer_geometry.IsEmpty() or not layer_geometry.IsValid():
            return 'Geometry is empty or topologically invalid; no repair is performed.'
        return None

    def transform(self, features, report, destination, scratch_dir, coordinate_operation=None):
        """Only CityGISOO transforms coordinates; JSON owns authoritative attributes."""
        from citygisoo import ScrubLayer
        from qgis.core import QgsApplication, QgsCoordinateReferenceSystem, QgsProject
        source = Path(scratch_dir) / 'geometry-source.geojson'
        transformed = Path(scratch_dir) / 'geometry-wgs84.geojson'
        bridge = {'type': 'FeatureCollection', 'crs': {
            'type': 'name', 'properties': {'name': report['source_crs']}}, 'features': [
                {'type': 'Feature', 'id': f['id'], 'geometry': f['geometry'],
                 'properties': {'sim_prepared_id': f['id']}} for f in features]}
        with source.open('x', encoding='utf-8') as stream:
            json.dump(bridge, stream, allow_nan=False)
        from collections import defaultdict
        from osgeo import ogr
        from qgis.core import (QgsCoordinateTransformContext, QgsFeature, QgsField,
                               QgsGeometry, QgsVectorLayer, QgsWkbTypes)
        from qgis.PyQt.QtCore import QMetaType
        groups = defaultdict(list)
        for feature in features:
            points = feature['geometry']['coordinates']
            if feature['geometry']['type'] == 'MultiPolygon':
                points = points[0]
            groups[(feature['geometry']['type'], len(points[0][0]))].append(feature)
        final, provider_ids = [], []
        expected_crs = QgsCoordinateReferenceSystem(report['source_crs'])
        context = QgsCoordinateTransformContext(QgsProject.instance().transformContext())
        if coordinate_operation:
            context.addCoordinateOperation(expected_crs, QgsCoordinateReferenceSystem(TARGET_CRS),
                                           coordinate_operation, False)
        for group_index, group in enumerate(groups.values()):
            layer = None
            scrub = None
            try:
                first = QgsGeometry()
                first.fromWkb(bytes(ogr.CreateGeometryFromJson(
                    json.dumps(group[0]['geometry'])).ExportToWkb()))
                layer = QgsVectorLayer(QgsWkbTypes.displayString(first.wkbType()),
                                       'scenario_001_preparation', 'memory')
                layer.setCrs(expected_crs)
                provider = layer.dataProvider()
                if not provider.addAttributes([QgsField('sim_prepared_id', QMetaType.Type.LongLong)]):
                    raise ValueError('Could not create identity staging field.')
                layer.updateFields()
                for feature in group:
                    geometry = QgsGeometry()
                    geometry.fromWkb(bytes(ogr.CreateGeometryFromJson(
                        json.dumps(feature['geometry'])).ExportToWkb()))
                    staged = QgsFeature(layer.fields())
                    staged.setAttributes([feature['id']])
                    staged.setGeometry(geometry)
                    if not provider.addFeatures([staged])[0]:
                        raise ValueError('Could not stage an eligible geometry.')
                layer.updateExtents()
                # Override only source loading: all coordinate transformations and
                # round-trip checks remain the generic CityGISOO implementation.
                class MemoryScrubLayer(ScrubLayer):
                    def load_layer(self):
                        return layer
                scrub = MemoryScrubLayer(QgsApplication.prefixPath(), str(source),
                                         'scenario_001_preparation')
                if not scrub.layer.isValid() or scrub.layer.crs() != expected_crs:
                    raise ValueError('Staging CRS disagrees with verified source CRS.')
                if transformed.exists():
                    transformed.unlink()
                scrub.reproject_layer(TARGET_CRS, str(transformed), transform_context=context,
                                      source_fid_field='sim_provider_fid')
                with transformed.open(encoding='utf-8') as stream:
                    exported = json.load(stream)
                original = {f['id']: f for f in group}
                for feature in exported['features']:
                    identifier = feature['properties']['sim_prepared_id']
                    if type(identifier) is not int or identifier not in original:
                        raise ValueError('Reprojection lost a prepared identity.')
                    output = deepcopy(original[identifier])
                    if geometry_structure(feature['geometry']) != geometry_structure(output['geometry']):
                        raise ValueError('Reprojection changed parts, rings or coordinate dimensions.')
                    # Equal CRSs require a separate export but no coordinate changes,
                    # including no loss from the intermediate writer's decimal precision.
                    if report['status'] != 'copied':
                        output['geometry'] = feature['geometry']
                    final.append(output)
                    provider_ids.append({'prepared_id': identifier, 'group': group_index,
                                         'provider_fid': feature['properties']['sim_provider_fid']})
            finally:
                if scrub is not None:
                    scrub.layer = None
                scrub = None
                layer = None
                gc.collect()
        order = {f['id']: i for i, f in enumerate(features)}
        final.sort(key=lambda f: order[f['id']])
        verify_final(final, features, equivalent=report['status'] == 'copied')
        with Path(destination).open('x', encoding='utf-8') as stream:
            json.dump({'type': 'FeatureCollection', 'features': final}, stream,
                      ensure_ascii=False, allow_nan=False)
        with Path(destination).open(encoding='utf-8') as stream:
            roundtrip = json.load(stream)
        if 'crs' in roundtrip:
            raise ValueError('Final WGS84 GeoJSON must omit legacy CRS declarations.')
        verify_final(roundtrip['features'], features, equivalent=report['status'] == 'copied')
        report['provider_ids'] = provider_ids
        report['output_location'] = str(destination)
        report['coordinate_operation_requested'] = coordinate_operation
        report['axis_order'] = 'longitude,latitude'
        logger.info('preparation_reprojection', extra={k: v for k, v in report.items()
                                                     if k != 'provider_ids'})
