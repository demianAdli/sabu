"""
Sabu project
jug_lca_buildings package
fixtures module
Licensed under the Apache License, Version 2.0.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
from dataclasses import dataclass, field
from typing import List

# To instantiate fake objects for testing the methods


@dataclass
class FakeLayer:
    no_mass: bool = False
    material_name: str = 'Cast Concrete'
    thickness: float = 0.1
    density: float = 2000.0


@dataclass
class FakeOpening:
    area: float = 2.5  # m2


@dataclass
class FakeBoundary:
    layers: List[FakeLayer] = field(default_factory=list)
    opaque_area: float = 100.0
    thickness: float = 0.2
    window_ratio: float = 0.0
    thermal_openings: List[FakeOpening] = field(default_factory=list)


@dataclass
class FakeSurface:
    associated_thermal_boundaries: List[FakeBoundary] = \
        field(default_factory=list)
    type: str = 'Wall'  # Use 'Roof' to trigger skylight logic for >=2020


@dataclass
class FakeBuilding:
    surfaces: List[FakeSurface] = field(default_factory=list)
    year_of_construction: int = 1995
    function: str = 'Residential'

#  Factory helpers


def make_layer(**overrides) -> FakeLayer:
    return FakeLayer(**overrides)


def make_boundary(layers=None, **overrides) -> FakeBoundary:
    if layers is None:
        layers = [
            make_layer(
                no_mass=False,
                material_name='Cast Concrete',
                thickness=0.10,
                density=2000.0),
            make_layer(
                no_mass=True,
                material_name='virtual_no_mass_53',
                thickness=0.0,
                density=None),
            make_layer(
                no_mass=False,
                material_name='Timber Flooring',
                thickness=0.01,
                density=650.0),
        ]

    if 'thickness' not in overrides:
        derived = sum(layer.thickness for layer in layers if not layer.no_mass)
        overrides['thickness'] = derived
        
    return FakeBoundary(layers=layers, **overrides)


def make_surface(boundaries=None, **overrides) -> FakeSurface:
    if boundaries is None:
        boundaries = [make_boundary()]
    return FakeSurface(associated_thermal_boundaries=boundaries, **overrides)


def make_building(surfaces=None, **overrides) -> FakeBuilding:
    if surfaces is None:
        surfaces = [make_surface()]
    return FakeBuilding(surfaces=surfaces, **overrides)


# For windows boundary
def with_openings(
        boundary: FakeBoundary, count=2, opening_area=2.5, window_ratio=0.3) \
        -> FakeBoundary:
    boundary.window_ratio = window_ratio
    boundary.thermal_openings = \
        [FakeOpening(area=opening_area) for _ in range(count)]
    return boundary
