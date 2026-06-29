import os
import numpy as np
import pandas as pd
from typing import Optional
from utils.logger import setup_logger
from data_sources.base_survey_trip import BaseSurveyTrip
from models.mode_types import (
    MODE_CAR, MODE_BUS, MODE_RAIL, MODE_WALK, MODE_BIKE,
    MODE_SCHOOL_BUS, MODE_RIDESHARE, MODE_OTHER
)

logger = setup_logger(__name__)

class ChicagoSurveyTrip(BaseSurveyTrip):
    """Chicago Survey (TRACT-based spatial system)."""

    RAW_COLUMNS = [
        'person_id', 'mode_type',
        'o_tract_2020', 'd_tract_2020',
        'o_purpose_category', 'd_purpose_category',
        'depart_date', 'depart_hour', 'depart_minute', 'depart_seconds',
        'arrive_date', 'arrive_hour', 'arrive_minute', 'arrive_second',
        'duration_seconds', 'distance_miles', 'trip_weight',
        'trip_survey_complete'
    ]

    COLUMN_MAP = {
        'o_tract_2020': BaseSurveyTrip.ORIGIN_LOC,
        'd_tract_2020': BaseSurveyTrip.DESTINATION_LOC,
        'o_purpose_category': BaseSurveyTrip.ORIGIN_PURPOSE,
        'd_purpose_category': BaseSurveyTrip.DESTINATION_PURPOSE,
    }

    # Maps strings safely to canonical constants matching project casing rules
    PURPOSE_MAP = {
        '1': BaseSurveyTrip.ACT_HOME,       '1.0': BaseSurveyTrip.ACT_HOME,
        '2': BaseSurveyTrip.ACT_WORK,       '2.0': BaseSurveyTrip.ACT_WORK,
        '3': BaseSurveyTrip.ACT_WORK,       '3.0': BaseSurveyTrip.ACT_WORK,          # Work related -> Work
        '4': BaseSurveyTrip.ACT_SCHOOL,     '4.0': BaseSurveyTrip.ACT_SCHOOL,
        '5': BaseSurveyTrip.ACT_SCHOOL,     '5.0': BaseSurveyTrip.ACT_SCHOOL,        # School related -> School
        '6': BaseSurveyTrip.ACT_ESCORT,     '6.0': BaseSurveyTrip.ACT_ESCORT,        # Escort -> Escort
        '7': BaseSurveyTrip.ACT_SHOPPING,   '7.0': BaseSurveyTrip.ACT_SHOPPING,      # Shop -> Shopping
        '8': BaseSurveyTrip.ACT_DINING,     '8.0': BaseSurveyTrip.ACT_DINING,        # Meal -> Dining
        '9': BaseSurveyTrip.ACT_SOCIAL,     '9.0': BaseSurveyTrip.ACT_SOCIAL,        # Social/recreational -> Social
        '10': BaseSurveyTrip.ACT_OTHER,     '10.0': BaseSurveyTrip.ACT_OTHER,        # Errand -> Other
        '11': BaseSurveyTrip.ACT_OTHER,     '11.0': BaseSurveyTrip.ACT_OTHER,        # Change mode -> Other
        '12': BaseSurveyTrip.ACT_OTHER,     '12.0': BaseSurveyTrip.ACT_OTHER,        # Overnight -> Other
        '13': BaseSurveyTrip.ACT_OTHER,     '13.0': BaseSurveyTrip.ACT_OTHER,        # Other -> Other
    }

    # Maps strings safely to canonical constants matching project casing rules
    MODE_MAP = {
        '1': BaseSurveyTrip.MODE_WALK,         '1.0': BaseSurveyTrip.MODE_WALK,
        '2': BaseSurveyTrip.MODE_BIKE,         '2.0': BaseSurveyTrip.MODE_BIKE,
        '4': BaseSurveyTrip.MODE_RIDESHARE,    '4.0': BaseSurveyTrip.MODE_RIDESHARE,    # Scooter share -> rideshare
        '5': BaseSurveyTrip.MODE_OTHER,        '5.0': BaseSurveyTrip.MODE_OTHER,        # Taxi -> other
        '6': BaseSurveyTrip.MODE_RIDESHARE,    '6.0': BaseSurveyTrip.MODE_RIDESHARE,    # TNC -> rideshare
        '7': BaseSurveyTrip.MODE_OTHER,        '7.0': BaseSurveyTrip.MODE_OTHER,        # Other -> other
        '8': BaseSurveyTrip.MODE_CAR,          '8.0': BaseSurveyTrip.MODE_CAR,
        '9': BaseSurveyTrip.MODE_RIDESHARE,    '9.0': BaseSurveyTrip.MODE_RIDESHARE,    # Carshare -> rideshare
        '10': BaseSurveyTrip.MODE_SCHOOL_BUS,  '10.0': BaseSurveyTrip.MODE_SCHOOL_BUS,  # School bus -> school_bus
        '11': BaseSurveyTrip.MODE_RIDESHARE,   '11.0': BaseSurveyTrip.MODE_RIDESHARE,  # Shuttle/vanpool -> rideshare
        '12': BaseSurveyTrip.MODE_OTHER,       '12.0': BaseSurveyTrip.MODE_OTHER,       # Ferry -> other
        '13': BaseSurveyTrip.MODE_BUS,         '13.0': BaseSurveyTrip.MODE_BUS,         # Transit -> bus
        '14': BaseSurveyTrip.MODE_OTHER,       '14.0': BaseSurveyTrip.MODE_OTHER        # Long distance passenger -> other
    }

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config or {})
        self.metadata = {
            'source_type': 'chicagoSurvey'
        }

    # ─────────────────────────────────────────────
    # EXTRACT
    # ─────────────────────────────────────────────
    def extract_data(self, year: str, file_path: str) -> pd.DataFrame:
        df = pd.read_csv(
            file_path,
            usecols=self.RAW_COLUMNS,
            low_memory=False
        )

        # Missing codes
        MISSING_CODES = [995, '995', -1, '-1']
        df.replace(MISSING_CODES, np.nan, inplace=True)

        # Build datetime
        df['depart_time'] = pd.to_datetime(
            df['depart_date'].astype(str) + ' ' +
            df['depart_hour'].astype(str).str.zfill(2) + ':' +
            df['depart_minute'].astype(str).str.zfill(2) + ':' +
            df['depart_seconds'].astype(str).str.zfill(2),
            errors='coerce'
        )

        df['arrive_time'] = pd.to_datetime(
            df['arrive_date'].astype(str) + ' ' +
            df['arrive_hour'].astype(str).str.zfill(2) + ':' +
            df['arrive_minute'].astype(str).str.zfill(2) + ':' +
            df['arrive_second'].astype(str).str.zfill(2),
            errors='coerce'
        )

        self.data = df
        self.metadata['source_year'] = year

        return df

    # ─────────────────────────────────────────────
    # CLEAN (TRACT-BASED)
    # ─────────────────────────────────────────────
    def clean_data(self,
                   duration_std_multiplier: float = 3.0,
                   distance_std_multiplier: float = 3.0) -> None:

        if self.data is None:
            raise ValueError("No data loaded.")

        df = self.data.copy()
        initial_count = len(df)

        logger.info(f"Starting Chicago cleaning: {initial_count}")

        # Basic filters
        df = df[
            (df['trip_survey_complete'] == 1) &
            (df['mode_type'].notna()) &
            (df['depart_time'].notna()) &
            (df['arrive_time'].notna()) &
            (df['arrive_time'] >= df['depart_time']) &
            (df['duration_seconds'] > 0) &
            (df['distance_miles'] >= 0) &
            (df['o_tract_2020'].notna()) &
            (df['d_tract_2020'].notna())
        ]

        # Outliers
        df = df[df['duration_seconds'] <= df['duration_seconds'].mean() + duration_std_multiplier * df['duration_seconds'].std()]
        df = df[df['distance_miles'] <= df['distance_miles'].mean() + distance_std_multiplier * df['distance_miles'].std()]

        # Clean tract IDs
        for col in ['o_tract_2020', 'd_tract_2020']:
            df[col] = df[col].astype(str).str.replace('.0', '', regex=False).str.strip().str[:11]

        # Rename → canonical schema
        df.rename(columns=self.COLUMN_MAP, inplace=True)
        df[self.TRIP_WEIGHT] = df['trip_weight']

        # Purpose mapping (Safely maps clean strings while preserving exact constant capitalization)
        for col in [self.ORIGIN_PURPOSE, self.DESTINATION_PURPOSE]:
            df[col] = df[col].astype(str).str.replace('.0', '', regex=False).str.strip()
            df[col] = df[col].map(self.PURPOSE_MAP).fillna(self.ACT_OTHER)

        # Mode mapping (Safely maps clean strings while preserving exact constant capitalization)
        df[self.MODE_TYPE] = df[self.MODE_TYPE].astype(str).str.replace('.0', '', regex=False).str.strip()
        df[self.MODE_TYPE] = df[self.MODE_TYPE].map(self.MODE_MAP).fillna(self.MODE_OTHER)

        # Metadata
        df[self.SOURCE_TYPE] = self.metadata['source_type']
        df[self.SOURCE_YEAR] = self.metadata.get('source_year', '')

        final_count = len(df)
        logger.info(f"Cleaning complete: {final_count} (removed {initial_count - final_count})")

        self.data = df
        
        self.validate_schema()
        lengths = df[self.ORIGIN_LOC].astype(str).str.len().value_counts()
        print(lengths)
        self.detect_geo_level()