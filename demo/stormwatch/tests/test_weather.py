"""Tests for Stormwatch weather module."""

import pytest
from weather import (
    WeatherData,
    get_weather,
    get_forecast,
    format_forecast,
    CONDITIONS
)


class TestWeatherData:
    """Test WeatherData dataclass."""

    def test_create_weather_data(self):
        """Test creating weather data."""
        data = WeatherData(
            city="Test City",
            temperature=72.5,
            condition="Sunny",
            humidity=45,
            wind_speed=10.0
        )
        assert data.city == "Test City"
        assert data.temperature == 72.5

    def test_weather_data_str(self):
        """Test string representation."""
        data = WeatherData(
            city="SF",
            temperature=68.0,
            condition="Foggy",
            humidity=80,
            wind_speed=5.5
        )
        output = str(data)
        assert "SF" in output
        assert "68.0°F" in output
        assert "Foggy" in output


class TestGetWeather:
    """Test weather fetching."""

    def test_get_weather_returns_data(self):
        """Test that get_weather returns WeatherData."""
        result = get_weather("New York")
        assert isinstance(result, WeatherData)
        assert result.city == "New York"

    def test_weather_has_valid_condition(self):
        """Test that condition is from valid set."""
        result = get_weather("Chicago")
        assert result.condition in CONDITIONS

    def test_weather_temperature_in_range(self):
        """Test temperature is reasonable."""
        result = get_weather("Miami")
        assert 32 <= result.temperature <= 95

    def test_weather_humidity_in_range(self):
        """Test humidity is valid percentage."""
        result = get_weather("Seattle")
        assert 0 <= result.humidity <= 100


class TestForecast:
    """Test forecast functionality."""

    def test_forecast_returns_list(self):
        """Test forecast returns list of weather data."""
        result = get_forecast("Boston", days=3)
        assert isinstance(result, list)
        assert len(result) == 3

    def test_forecast_default_days(self):
        """Test default forecast is 3 days."""
        result = get_forecast("Denver")
        assert len(result) == 3

    def test_forecast_custom_days(self):
        """Test custom day count."""
        result = get_forecast("Austin", days=7)
        assert len(result) == 7

    def test_format_forecast(self):
        """Test forecast formatting."""
        forecast = get_forecast("LA", days=2)
        output = format_forecast(forecast)
        assert "FORECAST" in output
        assert "Day 1" in output
        assert "Day 2" in output
