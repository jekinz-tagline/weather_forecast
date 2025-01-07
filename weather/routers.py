import requests
import json
import os
from flask_smorest import Blueprint
from flask.views import MethodView
from flask import render_template
from datetime import datetime

weather_bp = Blueprint("weather", __name__)

@weather_bp.route("/weather")
class WeatherClass(MethodView):
    def get(self):
        # URL to fetch hourly and daily data
        url = (
            "http://my.meteoblue.com/packages/basic-1h_basic-day"
            "?lat=47.56&lon=7.57"
            "&temperature=F"
            "&history_days=4"
            "&forecast_days=5"
            "&temperature=F"
            "&apikey=uxSEMWd625F9VR3K"
        )
        try:
            # Make the HTTP GET request
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for HTTP errors

            # Get the JSON data from the response
            data = response.json()

            # Extract hourly data and daily data
            data_1h = data.get("data_1h", {})
            data_day = data.get("data_day", {})

            # Aggregate hourly data into 12-hour intervals
            twelve_hour_data = self.aggregate_to_12h(data_1h)

            # Prepare the data to be updated in the weather_data.json
            result = {
                "12_hour_data": twelve_hour_data,
                "daily_data": data_day,
            }

            # Path to the weather_data.json file
            file_path = "weather_data.json"

            # Check if the file exists
            if os.path.exists(file_path):
                # Read the existing data from the file
                with open(file_path, "r") as file:
                    existing_data = json.load(file)

                # Update the existing data with new data (only update relevant parts)
                existing_data.update(result["12_hour_data"])

                # Write the updated data back to the file
                with open(file_path, "w") as file:
                    json.dump(existing_data, file, indent=4)
            else:
                # If file doesn't exist, create a new one
                with open(file_path, "w") as file:
                    json.dump(result["12_hour_data"], file, indent=4)

            # Pass the data to the template for rendering
            return render_template("weather_table.html", data=result)

        except requests.exceptions.RequestException as e:
            # Handle exceptions and return an error response
            return {"error": str(e)}, 500

    def aggregate_to_12h(self, hourly_data):
        """
        Aggregates hourly data into 12-hour intervals for multiple fields.
        """
        time_series = hourly_data.get("time", [])
        fields = {key: hourly_data.get(key, []) for key in hourly_data if key != "time"}

        if not time_series or not fields:
            return {"error": "Hourly data is empty or missing"}

        twelve_hour_data = {"time": []}
        for field, values in fields.items():
            twelve_hour_data[field] = []

        interval_start = None
        field_sums = {field: 0.0 for field in fields}  # Initialize with float values
        field_counts = {field: 0 for field in fields}

        for time_str, *field_values in zip(time_series, *fields.values()):
            current_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
            if interval_start is None:
                interval_start = current_time

            field_values_float = [
                float(value) if value not in [None, ""] else 0.0 for value in field_values
            ]

            if (current_time - interval_start).total_seconds() >= 12 * 3600:
                twelve_hour_data["time"].append(interval_start.strftime("%Y-%m-%d %H:%M"))
                for field, field_value in zip(fields, field_values_float):
                    # Round and format to 2 decimal places for non-rainspot fields
                    mean_value = (
                        field_sums[field] / field_counts[field]
                        if field_counts[field]
                        else None
                    )

                    if field == "rainspot" and mean_value is not None:
                        # Scale the value down by 10^47 for 'rainspot' only
                        scaled_value = mean_value / (10 ** 47)

                        # Format the scaled value to two decimal places for 'rainspot' only
                        formatted_mean_value = round(scaled_value, 2)
                    else:
                        # Round other fields to 2 decimal places
                        formatted_mean_value = round(mean_value, 2) if mean_value is not None else 0.00

                    twelve_hour_data[field].append(formatted_mean_value)

                # Start a new interval
                interval_start = current_time
                for field, value in zip(fields, field_values_float):
                    field_sums[field] = value
                    field_counts[field] = 1
            else:
                # Accumulate data within the interval
                for field, value in zip(fields, field_values_float):
                    field_sums[field] += value
                    field_counts[field] += 1

        # Add the final interval if any data is left
        if all(count > 0 for count in field_counts.values()):
            twelve_hour_data["time"].append(interval_start.strftime("%Y-%m-%d %H:%M"))
            for field in fields:
                mean_value = (
                    field_sums[field] / field_counts[field]
                    if field_counts[field]
                    else None
                )

                if field == "rainspot" and mean_value is not None:
                    # Scale the value down by 10^47 for 'rainspot' only
                    scaled_value = mean_value / (10 ** 47)

                    # Format the scaled value to two decimal places for 'rainspot' only
                    formatted_mean_value = round(scaled_value, 2)
                else:
                    # Round other fields to 2 decimal places
                    formatted_mean_value = round(mean_value, 2) if mean_value is not None else 0.00

                twelve_hour_data[field].append(formatted_mean_value)

        return twelve_hour_data
