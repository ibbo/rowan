"""Rebuild the same search views/indexes used by the nightly SCDDB import."""
from refresh_scddb import postprocess_views_indexes_fts, sanity_print


if __name__ == '__main__':
    postprocess_views_indexes_fts()
    sanity_print()
