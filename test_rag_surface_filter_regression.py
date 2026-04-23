import sys
import unittest

sys.path.insert(0, "/Users/diegogarcia/Aplicaciones IA/Servicio-Al-Cliente-FERREINOX-SAS-BIC")

from backend.main import _filter_profiles_by_surface_compatibility


class RagSurfaceFilterRegressionTests(unittest.TestCase):
    def test_supported_surface_is_not_restricted_when_profile_data_is_mirrored(self):
        profiles = [
            {
                "canonical_family": "PINTUCOAT",
                "profile_json": {
                    "surface_targets": ["piso", "concreto", "interior"],
                    "restricted_surfaces": ["piso", "metal"],
                    "solution_guidance": {"restricted_surfaces": ["piso", "metal"]},
                    "commercial_context": {"recommended_uses": ["piso industrial", "concreto"]},
                },
            }
        ]

        restricted = _filter_profiles_by_surface_compatibility(profiles, ["piso"], query_text="piso de garaje residencial")

        self.assertEqual(restricted, [])

    def test_supported_surface_is_not_restricted_by_specialty_mentions(self):
        profiles = [
            {
                "canonical_family": "PINTUCOAT",
                "profile_json": {
                    "surface_targets": ["piso", "concreto", "interior"],
                    "restricted_surfaces": [],
                    "solution_guidance": {"restricted_surfaces": []},
                    "commercial_context": {
                        "recommended_uses": [
                            "Usado en pisos industriales",
                            "Apto para inmersion de aguas no potables",
                            "concreto",
                        ]
                    },
                },
            }
        ]

        restricted = _filter_profiles_by_surface_compatibility(profiles, ["piso"], query_text="piso de garaje residencial")

        self.assertEqual(restricted, [])

    def test_true_restricted_surface_is_still_blocked(self):
        profiles = [
            {
                "canonical_family": "KORAZA INTERIOR",
                "profile_json": {
                    "surface_targets": ["muro", "interior"],
                    "restricted_surfaces": ["piso"],
                    "solution_guidance": {"restricted_surfaces": ["piso"]},
                    "commercial_context": {"recommended_uses": ["muro interior"]},
                },
            }
        ]

        restricted = _filter_profiles_by_surface_compatibility(profiles, ["piso"], query_text="piso de bodega")

        self.assertEqual(restricted, ["KORAZA INTERIOR"])


if __name__ == "__main__":
    unittest.main()