import unittest

from crawler.normalization import normalize_openlibrary_book


class OpenLibraryNormalizationTests(unittest.TestCase):
    def test_children_book_maps_to_children_taxonomy_and_low_spice(self) -> None:
        raw_book = {
            "title": "Maple Grove Mystery",
            "authors": [{"name": "Ari Finch"}],
            "description": {
                "value": "A clean adventure where kids form a chosen family."
            },
            "subjects": [
                "Juvenile fiction",
                "Children",
                "Adventure stories",
                "Found family",
                "Friends to lovers",  # ignored by age/spice logic
            ],
        }

        normalized = normalize_openlibrary_book(raw_book)

        self.assertEqual(normalized["title"], "Maple Grove Mystery")
        self.assertEqual(normalized["authors"], ["Ari Finch"])
        self.assertIn("children", normalized["canonical_genres"])
        self.assertIn("adventure", normalized["canonical_genres"])
        self.assertIn("found-family", normalized["canonical_plot_tags"])
        self.assertEqual(normalized["age_band"], "middle-grade")
        self.assertEqual(normalized["spice_level"], "spice-1-none")

    def test_ya_payload_maps_to_ya_genres_and_medium_spice(self) -> None:
        raw_book = {
            "title": "Orbit Hearts",
            "authors": [
                {"author": {"name": "Dev Morgan"}},
                {"name": "Rin Vale"},
            ],
            "description": "A young adult slow burn romance in a space academy.",
            "subjects": [
                "Young adult fiction",
                "Science fiction",
                "Space opera",
                "Slow burn",
                "Rivals",
                "Competition",
                "Teenagers",
                "Steamy",
            ],
        }

        normalized = normalize_openlibrary_book(raw_book)

        self.assertEqual(normalized["authors"], ["Dev Morgan", "Rin Vale"])
        self.assertIn("young-adult", normalized["canonical_genres"])
        self.assertIn("science-fiction", normalized["canonical_genres"])
        self.assertIn("slow-burn-romance", normalized["canonical_plot_tags"])
        self.assertIn("competition", normalized["canonical_plot_tags"])
        self.assertIn("rivals", normalized["canonical_character_dynamics"])
        self.assertEqual(normalized["age_band"], "young-adult")
        self.assertEqual(normalized["spice_level"], "spice-3-moderate")

    def test_adult_payload_maps_to_high_spice(self) -> None:
        raw_book = {
            "title": "Velvet Vows",
            "authors": ["C. Hale"],
            "description": (
                "An adult dark romance with open door scenes and explicit scenes."
            ),
            "subjects": [
                "Romance fiction",
                "Dark romance",
                "Open door",
                "Explicit scenes",
                "Enemies to lovers",
                "Forbidden love",
            ],
            "subject_places": ["London"],
        }

        normalized = normalize_openlibrary_book(raw_book)

        self.assertIn("romance", normalized["canonical_genres"])
        self.assertIn("forbidden-love", normalized["canonical_plot_tags"])
        self.assertIn(
            "enemies-to-lovers",
            normalized["canonical_character_dynamics"],
        )
        self.assertEqual(normalized["age_band"], "adult")
        self.assertEqual(normalized["spice_level"], "spice-4-high")


if __name__ == "__main__":
    unittest.main()
