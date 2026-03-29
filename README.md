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

```json
{
  "battery": "Battery Type",
  "timestamp": "2024-06-01T12:00:00Z",
  "data": {
    "voltage": 3.7,
    "current": 1.5,
    "temperature": 25.0,
    "capacity": 2000,
    "cycle_count": 100
  }
}
```

For calculateInternalResistance() I kinda had GH Copilot do that for me
since I kinda don't know how to do big data like that, sorry guys </3