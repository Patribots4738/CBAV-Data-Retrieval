# CBAV Data Retrieval

Tools for running CBA tests and exporting parsed data.

## Configuration

All config should be done in a .env file placed inside the `src` folder.
This is so all important code is separated from regular repository stuff.

## Usage

1. Install dependencies:
   `uv sync`
2. Copy the .env.example file to .env and fill in the database url and battery info (See the CBA app for battery types).
3. Plug in your CBA unit with a battery
4. Run the script from the root of the repository
   `python ./src/main.py`
5. profit

## What it sends

The script sends JSON data to the database URL via a POST request. The data structure will look like the following:
It is meant to work with our own [battery website](https://github.com/Patribots4738/BatteryWebsite), and the data is structured for that.

```json
{
   "batteryNumber": 17,
   "header": {
      "date": {
         "year": 1928,
         "month": 4,
         "day": 12
      },
      "time": {
         "hour": 16,
         "time": 3,
         "second": 45
      },
      "initialVoltage": 13.192,
      "internalResistance": 0.021
  },
   "datapoints": {
        "0": {
             "time": 0,
             "voltage": 13.192,
             "current": 0.0
        },
        "1": {
             "time": 1,
             "voltage": 13.183,
             "current": 1.0
        }
   }
}
```

For calculateInternalResistance() I kinda had GH Copilot do that for me
since I kinda don't know how to do big data like that, sorry guys </3