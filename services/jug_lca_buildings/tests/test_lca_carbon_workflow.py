"""
Sabu project
jug_lca_buildings package
test_lca_carbon_workflow module
Licensed under the Apache License, Version 2.0.
Project Designer and Developer: Alireza Adli
alireza.adli@mail.concordia.ca
alireza.adli4@gmail.com
www.demianadli.com
"""
from unittest import TestCase
from unittest.mock import Mock, patch, call
from src.jug_lca_buildings.lca_carbon_workflow import LCACarbonWorkflow
from tests.fixtures import (
    make_building, make_surface, make_boundary, make_layer, with_openings
)


class TestLCACarbonWorkflow(TestCase):
    def setUp(self):
        # Avoids running the constructor
        # test_lca_wf wf is short for workflow. This is the test instance.
        self.test_lca_wf = object.__new__(LCACarbonWorkflow)
        self.test_lca_wf.nrcan_catalogs = Mock()

        # Material catalogs used by both envelope and opening paths
        materials = {
            'Cast Concrete': {
                'embodied_carbon': 230,
                'recycling_ratio': 0.8,
                'onsite_recycling_ratio': 0,
                'company_recycling_ratio': 1,
                'landfilling_ratio': 0.2,
            },
            'Timber Flooring': {
                'embodied_carbon': 10.33,
                'recycling_ratio': 0.8,
                'onsite_recycling_ratio': 0,
                'company_recycling_ratio': 1,
                'landfilling_ratio': 0.2,
            },
        }
        self.test_lca_wf.nrcan_catalogs.search_material.side_effect = \
            lambda name: materials[name]

        # Opaque-surface code lookup used by opening path
        self.test_lca_wf.nrcan_catalogs.\
            find_opaque_surface.return_value = '8'
        self.test_lca_wf.nrcan_catalogs.\
            hub_to_nrcan_function.return_value = 'MidriseApartment'
        self.test_lca_wf.nrcan_catalogs.\
            year_to_period_of_construction.return_value = '1000_1900'

        # Transparent surfaces lookup must accept
        # (transparent_surface_type, opaque_surface_code)
        windows = {
            ('Window',   '1000_1900_8'):
                {'embodied_carbon': 86.79,
                 'mass_per_unit unit': 39.49,
                 'recycling_ratio': 0.85,
                 'onsite_recycling_ratio': 0.5,
                 'company_recycling_ratio': 0.5,
                 'landfilling_ratio': 0.15},
            ('Skylight', '2020_3000_6'):
                {'embodied_carbon': 94.5,
                 'mass_per_unit unit': 39.49,
                 'recycling_ratio': 0.85,
                 'onsite_recycling_ratio': 0.5,
                 'company_recycling_ratio': 0.5,
                 'landfilling_ratio': 0.10},
        }
        self.test_lca_wf.nrcan_catalogs.\
            search_transparent_surfaces.side_effect = \
            lambda window_type, opaque: windows[(window_type, opaque)]

    # eol is short for end-of-life
    @patch('src.jug_lca_buildings.lca_carbon_workflow.EndOfLifeEmission')
    @patch('src.jug_lca_buildings.lca_carbon_workflow.EnvelopeEmission')
    def test_calculate_envelope_emission(
            self, envelope_emission_mock, envelope_eol_emission_mock):
        # Arrange a boundary using the factory
        boundary = make_boundary(opaque_area=154.1857854127884)

        # Patch collaborators with deterministic returns
        def envelope_emission_mock_constructor(
                embodied_factor, thickness, area, density):
            mock = Mock()
            mock.calculate_envelope_emission.return_value = \
                embodied_factor * thickness * area * density
            return mock
        envelope_emission_mock.side_effect = \
            envelope_emission_mock_constructor

        def envelope_eol_emission_mock_constructor(
                recycling_ratio,
                onsite_recycling_ratio,
                company_recycling_ratio,
                landfilling_ratio,
                workload):
            mock = Mock()
            mock.calculate_end_of_life_emission.return_value = 100.0 * workload
            return mock
        envelope_eol_emission_mock.side_effect = \
            envelope_eol_emission_mock_constructor

        # Test
        layer_embodied, layer_eol = \
            self.test_lca_wf._calculate_envelope_emission(boundary)

        # Assert (no-mass skipped; 2 layers used)
        self.assertEqual(len(layer_embodied), 2)
        self.assertEqual(len(layer_eol), 2)

    @patch('src.jug_lca_buildings.lca_carbon_workflow.EndOfLifeEmission')
    @patch('src.jug_lca_buildings.lca_carbon_workflow.OpeningEmission')
    def test_calculate_opening_emission_variants(
            self, opening_emission_mock, opening_eol_emission_mock):
        # Shared boundary: two openings of 3.0 m² each;
        # boundary thickness drives EoL workload
        boundary = with_openings(
            make_boundary(thickness=0.15, opaque_area=50.0),
            count=2, opening_area=3.0, window_ratio=0.25
        )

        # OpeningEmission returns factor * area (deterministic)
        def opening_emission_mock_constructor(embodied_factor, area):
            mock = Mock()
            mock.calculate_opening_emission.return_value = \
                embodied_factor * area
            return mock
        opening_emission_mock.side_effect = opening_emission_mock_constructor

        # EndOfLifeEmission returns
        # 10 * workload so we can assert workload correctness
        def opening_eol_emission_mock_constructor(
                recycling_ratio,
                onsite_recycling_ratio,
                company_recycling_ratio,
                landfilling_ratio,
                workload):
            mock = Mock()
            mock.calculate_end_of_life_emission.return_value = 10.0 * workload
            return mock
        opening_eol_emission_mock.side_effect = \
            opening_eol_emission_mock_constructor

        cases = [
            # 1: year of construction
            # 2: surface_type
            # 3: expected transparent type
            # 4: opaque code
            # 5: expected embodied factor
            # 6: expected mass per unit area
            # (1, 2, 3, 4, 5, 6)
            (1995, 'Wall',  'Window',   '1000_1900_8', 86.79, 39.49),
            (2022, 'Roof',  'Skylight', '2020_3000_6', 94.5, 39.49),
        ]

        for year, s_type, expected_ttype, opaque_code, factor, mass_per_unit in cases:
            with self.subTest(year=year, surface_type=s_type):
                # Reset per-case call histories
                opening_emission_mock.reset_mock()
                opening_eol_emission_mock.reset_mock()
                self.test_lca_wf.nrcan_catalogs.\
                    search_transparent_surfaces.reset_mock()

                surface = make_surface(boundaries=[boundary], type=s_type)
                building = make_building(surfaces=[surface],
                                         year_of_construction=year,
                                         function='Residential')

                opening_embodied, opening_eol = \
                    self.test_lca_wf._calculate_opening_emission(
                        building,
                        surface,
                        boundary,
                        opaque_surface_code=opaque_code
                    )

                # Two openings -> two values
                self.assertEqual(len(opening_embodied), 2)
                self.assertEqual(len(opening_eol), 2)

                # Catalog lookup used correct (type, code)
                self.test_lca_wf.nrcan_catalogs.\
                    search_transparent_surfaces.assert_called_with(
                     expected_ttype, opaque_code)

                # OpeningEmission called once per opening
                # with the right factor & area
                opening_emission_mock.assert_has_calls(
                    [call(factor, 3.0), call(factor, 3.0)], any_order=True)

                # EoL workload per opening = area * mass_per_unit
                w = 3.0 * mass_per_unit
                self.assertAlmostEqual(opening_eol[0], 10.0 * w, places=6)
                self.assertAlmostEqual(opening_eol[1], 10.0 * w, places=6)

    @patch.object(
        LCACarbonWorkflow, '_calculate_opening_emission', autospec=True)
    @patch.object(
        LCACarbonWorkflow, '_calculate_envelope_emission', autospec=True)
    def test_calculate_building_component_emission(
            self, calc_envelope_emission_mock, calc_opening_emission_mock):
        """
        Building with 2 surfaces:
        - Surface A: 1 boundary with openings ?
        both envelope & opening paths hit
        - Surface B: 1 boundary without openings ?
        only envelope path
        We return deterministic lists from
        the patched helpers and assert final sums.
        """
        # --- arrange a minimal building graph
        boundary_with_openings = with_openings(
            make_boundary(), count=2, opening_area=3.0, window_ratio=0.3)
        boundary_without_openings = make_boundary()  # window_ratio = 0.0

        surface_1 = make_surface(
            boundaries=[boundary_with_openings], type='Roof')
        surface_2 = make_surface(
            boundaries=[boundary_without_openings],   type='Wall')
        building = make_building(
            surfaces=[surface_1, surface_2],
            year_of_construction=2025, function='Residential')

        # Make the catalog lookups consistent with your SUT’s opaque code flow
        self.test_lca_wf.nrcan_catalogs.\
            hub_to_nrcan_function.return_value = 'MidriseApartment'
        self.test_lca_wf.nrcan_catalogs.\
            year_to_period_of_construction.return_value = '2020_3000'
        self.test_lca_wf.nrcan_catalogs.\
            find_opaque_surface.return_value = '2020_3000_6'

        # --- patch helpers with deterministic returns
        # Envelope: lists per boundary (embodied list, eol list)
        def calc_envelope_emission_side_effect(self_obj, boundary):
            if boundary is boundary_with_openings:
                return [10.0, 20.0], [1.0, 2.0]   # two massive layers
            if boundary is boundary_without_openings:
                return [5.0], [0.5]               # one massive layer
            self.fail('Unexpected boundary')
        calc_envelope_emission_mock.side_effect = \
            calc_envelope_emission_side_effect

        # Opening: only called for boundary_with_openings (two openings)
        def calc_opening_emission_side_effect(
                self_obj,
                building_arg,
                surface_arg,
                boundary_arg,
                opaque_code):
            self.assertIs(boundary_arg, boundary_with_openings)
            self.assertEqual(opaque_code, '2020_3000_6')
            # embodied per opening, eol per opening
            return [7.0, 8.0], [0.7, 0.8]
        calc_opening_emission_mock.side_effect = \
            calc_opening_emission_side_effect

        # --- Test
        env_sum, open_sum, comp_sum, \
            env_eol_sum, open_eol_sum, comp_eol_sum = \
            self.test_lca_wf.calculate_building_component_emission(building)

        # --- assert catalog lookups (once per building)
        self.test_lca_wf.nrcan_catalogs.\
            hub_to_nrcan_function.assert_called_once_with('Residential')
        self.test_lca_wf.nrcan_catalogs.\
            year_to_period_of_construction.assert_called_once_with(2025)
        self.test_lca_wf.nrcan_catalogs.\
            find_opaque_surface.assert_called_once_with(
             'MidriseApartment', '2020_3000', '6')

        # Helpers invoked expected number of times
        # two boundaries ? envelope twice
        self.assertEqual(calc_envelope_emission_mock.call_count, 2)
        # only the windowed boundary
        self.assertEqual(calc_opening_emission_mock.call_count, 1)

        # Totals:
        # envelope embodied = (10+20) + (5) = 35
        # opening  embodied = (7+8)        = 15
        # component embodied = 35 + 15     = 50
        self.assertAlmostEqual(env_sum, 35.0, places=6)
        self.assertAlmostEqual(open_sum, 15.0, places=6)
        self.assertAlmostEqual(comp_sum, 50.0, places=6)

        # envelope EoL = (1+2) + (0.5) = 3.5
        # opening  EoL = (0.7+0.8)     = 1.5
        # component EoL = 3.5 + 1.5    = 5.0
        self.assertAlmostEqual(env_eol_sum, 3.5, places=6)
        self.assertAlmostEqual(open_eol_sum, 1.5, places=6)
        self.assertAlmostEqual(comp_eol_sum, 5.0, places=6)

    def test__export_emissions_formats_all_keys(self):
        # Arrange
        # Avoid running the real calculation
        self.test_lca_wf.calculate_emission = Mock()

        # Pre-populate lists with two 'buildings'
        self.test_lca_wf.building_opening_emission = [2.0, 5.0]
        self.test_lca_wf.building_envelope_emission = [1.0, 4.0]
        self.test_lca_wf.building_component_emission = [3.0, 6.0]
        self.test_lca_wf.building_opening_end_of_life_emission = [20.0, 50.0]
        self.test_lca_wf.building_envelope_end_of_life_emission = [10.0, 40.0]
        self.test_lca_wf.building_component_end_of_life_emission = [30.0, 60.0]

        # Expected mapping from dict keys ? source lists
        expected_map = {
            'opening_embodied_emissions':
                self.test_lca_wf.building_opening_emission,
            'envelope_embodied_emissions':
                self.test_lca_wf.building_envelope_emission,
            'component_embodied_emissions':
                self.test_lca_wf.building_component_emission,
            'opening_end_of_life_emissions':
                self.test_lca_wf.building_opening_end_of_life_emission,
            'envelope_end_of_life_emissions':
                self.test_lca_wf.building_envelope_end_of_life_emission,
            'component_end_of_life_emissions':
                self.test_lca_wf.building_component_end_of_life_emission,
        }

        # Test
        result = self.test_lca_wf.export_emissions()

        # Assert: number of dicts equals number of buildings
        self.assertEqual(len(result), 2)

        # Check each key across all buildings
        for index, feature_dict in enumerate(result):
            for key, source_list in expected_map.items():
                # key exists
                self.assertIn(key, feature_dict)
                # value matches
                self.assertEqual(feature_dict[key], source_list[index])
