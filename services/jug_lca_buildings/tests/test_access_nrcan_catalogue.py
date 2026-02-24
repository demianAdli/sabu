from unittest import TestCase
from pathlib import Path

from src.jug_lca_buildings.life_cycle_assessment.access_nrcan_catalogue\
    import AccessNrcanCatalog


class TestAccessNRCANCatalog(TestCase):
    def setUp(self):
        self.path = Path(__file__).parent.parent / 'src' / 'jug_lca_buildings' / 'data'
        self.catalog = AccessNrcanCatalog(self.path)

    def test_hub_to_nrcan_function(self):
        test_cases = {
            'residential': 'MidriseApartment',
            'small hotel': 'SmallHotel'
        }

        for hub, expected in test_cases.items():
            with self.subTest(hub=hub):
                self.assertEqual(
                    self.catalog.hub_to_nrcan_function(hub),
                    expected
                )

    def test_year_to_period(self):
        test_cases = {
            1000: '1000_1900',
            1490: '1000_1900',
            1700: '1000_1900',
            1900: '1000_1900',
            1910: '1901_1910',
            1945: '1941_1950',
            1999: '1991_2000',
            2011: '2011_2016'
            }

        for year, expected in test_cases.items():
            with self.subTest(year=year):
                self.assertEqual(
                    self.catalog.year_to_period_of_construction(year), 
                    expected)
                
    def test_layers_outdoors_wall(self):
        result = self.catalog.layers('1000_1900_4', 'OutdoorsWall')
        self.assertEqual(result, {
            'Brickwork Outer': 0.1,
            'virtual_no_mass_0': 0,
            'Concrete Block (Medium)': 0.1,
            'Gypsum Plastering': 0.013
        })

    def test_layers_ground_floor(self):
        result = self.catalog.layers('1931_1940_8', 'GroundFloor')
        self.assertEqual(result, {
            'Cast Concrete': 0.1,
            'virtual_no_mass_179': 0,
            'Timber Flooring': 0.01
        })

    def test_layers_ground_roof_ceiling(self):
        result = self.catalog.layers('2020_3000_4', 'GroundRoofCeiling')
        self.assertEqual(result, {
            'Asphalt 1': 0.01,
            'virtual_no_mass_508': 0,
            'MW Glass Wool (rolls)': 0.05,
            'Plasterboard': 0.013
        })

    def test_search_material(self):
        test_cases = {
            'Urea Formaldehyde Foam': {
              'no_mass': False,
              'conductivity': 0.04,
              'density': 0.028,
              'specific_heat': 1400,
              'thermal_emittance': 0.9,
              'solar_absorptance': 0.6,
              'visible_absorptance': 0.6,
              'embodied_carbon': 3180,
              'recycling_ratio': 0.9,
              'onsite_recycling_ratio': 0,
              'company_recycling_ratio': 1,
              'landfilling_ratio': 0.1
            },
            'Lightweight Metallic Cladding': {
              'no_mass': False,
              'conductivity': 0.29,
              'density': 1.15,
              'specific_heat': 1000,
              'thermal_emittance': 0.9,
              'solar_absorptance': 0.4,
              'visible_absorptance': 0.4,
              'embodied_carbon': 29.73,
              'recycling_ratio': 0.98,
              'onsite_recycling_ratio': 0,
              'company_recycling_ratio': 1,
              'landfilling_ratio': 0.02
            }
        }

        for name, expected in test_cases.items():
            with self.subTest(material=name):
                self.assertEqual(
                    self.catalog.search_material(name), expected)
                
    def test_search_transparent_surfaces_window(self):
        result = self.catalog.search_transparent_surfaces(
            'Window', '2020_3000_7B')
        self.assertEqual(result, {
            'period_of_construction': '2020_3000',
            'climate_zone': '7B',
            'shgc': 0.49,
            'type': 'Window',
            'frame_ratio': 0,
            'u_value': 1.44,
            'mass_per_unit unit': 32.59,
            'embodied_carbon': 112,
            'recycling_ratio': 0.85,
            'onsite_recycling_ratio': 0.5,
            'company_recycling_ratio': 0.5,
            'landfilling_ratio': 0.1
        })

    def test_search_transparent_surfaces_skylight(self):
        result = self.catalog.search_transparent_surfaces(
            'Skylight', '2020_3000_7B')
        self.assertEqual(result, {
            'period_of_construction': '2020_3000',
            'climate_zone': '7B',
            'shgc': 0.49,
            'type': 'Skylight',
            'frame_ratio': 0,
            'u_value': 2.01,
            'mass_per_unit unit': 39.49,
            'embodied_carbon': 94.5,
            'recycling_ratio': 0.85,
            'onsite_recycling_ratio': 0.5,
            'company_recycling_ratio': 0.5,
            'landfilling_ratio': 0.1
        })

    def test_find_opaque_surface(self):
        test_cases = [
            ('FullServiceRestaurant', '1000_1900', '4', '1000_1900_4'),
            ('FullServiceRestaurant', '1901_1910', '4', '1901_1910_4'),
            ('FullServiceRestaurant', '1901_1910', '5', '1901_1910_5'),
        ]
        for function, vintage, zone, expected in test_cases:
            with self.subTest(function=function, vintage=vintage, zone=zone):
                self.assertEqual(
                    self.catalog.find_opaque_surface(function, vintage, zone),
                    expected
                )
                
