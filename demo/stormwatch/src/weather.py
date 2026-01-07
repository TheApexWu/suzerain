"""
Stormwatch - Simple weather CLI.

"The wind howled across the plain like the breath of some dark god."
"""

import argparse
import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class WeatherData:
    """Weather information for a location."""
    city: str
    temperature: float
    condition: str
    humidity: int
    wind_speed: float

    def __str__(self):
        return (
            f"{self.city}: {self.temperature}°F, {self.condition}\n"
            f"  Humidity: {self.humidity}%  Wind: {self.wind_speed} mph"
        )


# Simulated weather conditions
CONDITIONS = ["Sunny", "Cloudy", "Rainy", "Stormy", "Foggy", "Clear"]


def get_weather(city: str) -> WeatherData:
    """Fetch weather for a city (simulated)."""
    # In real app, this would call a weather API
    return WeatherData(
        city=city,
        temperature=round(random.uniform(32, 95), 1),
        condition=random.choice(CONDITIONS),
        humidity=random.randint(20, 90),
        wind_speed=round(random.uniform(0, 30), 1)
    )


def get_forecast(city: str, days: int = 3) -> list[WeatherData]:
    """Get multi-day forecast (simulated)."""
    return [get_weather(f"{city} (Day {i+1})") for i in range(days)]


def format_forecast(forecast: list[WeatherData]) -> str:
    """Format forecast for display."""
    lines = ["=" * 40, "FORECAST", "=" * 40]
    for day in forecast:
        lines.append(str(day))
        lines.append("-" * 40)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Stormwatch Weather CLI")
    parser.add_argument("--city", "-c", default="San Francisco",
                        help="City to check weather for")
    parser.add_argument("--forecast", "-f", type=int, metavar="DAYS",
                        help="Show N-day forecast")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Output as JSON")

    args = parser.parse_args()

    if args.forecast:
        forecast = get_forecast(args.city, args.forecast)
        print(format_forecast(forecast))
    else:
        weather = get_weather(args.city)
        print(weather)


if __name__ == "__main__":
    main()
