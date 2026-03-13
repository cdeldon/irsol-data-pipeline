"""Tests for the day processor MaxDeltaPolicy."""

import datetime

from irsol_data_pipeline.core.models import MaxDeltaPolicy


class TestMaxDeltaPolicy:
    def test_default_policy(self):
        policy = MaxDeltaPolicy()
        delta = policy.get_max_delta(wavelength=6302)
        assert delta == datetime.timedelta(hours=2)

    def test_custom_default(self):
        policy = MaxDeltaPolicy(default_max_delta=datetime.timedelta(hours=4))
        delta = policy.get_max_delta(wavelength=6302)
        assert delta == datetime.timedelta(hours=4)

    def test_subclass_override(self):
        class CustomPolicy(MaxDeltaPolicy):
            def get_max_delta(self, wavelength, instrument="", telescope=""):
                if wavelength < 5000:
                    return datetime.timedelta(hours=1)
                return self.default_max_delta

        policy = CustomPolicy()
        assert policy.get_max_delta(wavelength=4078) == datetime.timedelta(hours=1)
        assert policy.get_max_delta(wavelength=6302) == datetime.timedelta(hours=2)
