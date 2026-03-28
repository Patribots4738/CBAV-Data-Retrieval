import json
import os
import xml.etree.ElementTree as ElementTree
from datetime import datetime
from pathlib import Path
from subprocess import run

from dotenv import load_dotenv

from lib import wmr_cba

load_dotenv(dotenv_path='./src/.env')
env = os.environ

def check() -> int:
	while True:
		userInput = input("Enter the battery number: ")
		try:
			return int(userInput)
		except ValueError as e2:
			print("Invalid battery number.")
			print(f"Error {e2}")


def runMultipleDischargeTest(
		points: list[tuple[int, float]],
		cutoff_v: float,
		output_path: str,
		voltage: float,
		title: str = "Test",
) -> int:
	n = len(points)
	point_str = ",".join(f"{t},{a}" for t, a in points)
	multiple_arg = f"{n},{point_str}"
	
	WMRCBA = "C:\\Program Files (x86)\\West Mountain Radio\\CBA Software V3\\WMRCBA.exe"
	if not Path(WMRCBA).is_file():
		print("ERROR! CBA Software may not be installed!")
		exit(1)
	
	batteryData = f'{env.get("BATTERY_AH")},{env.get("BATTERY_CELLS")},{env.get("BATTERY_CELLS")},{voltage},{env.get("BATTERY_WEIGHT")},"{env.get("BATTERY_TYPE")}"'
	
	cmd = [
		WMRCBA,
		"/test",
		"multiple",
		multiple_arg,
		"/cutoff",
		str(cutoff_v),
		"/open",
		output_path,
		"/title",
		title,
		"/battery",
		batteryData
	]
	
	result = run(cmd)
	
	return result.returncode


def getVoltageFromCba():
	CBA = wmr_cba.cba4()
	devices = CBA.scan()
	if not devices:
		print("ERROR! No CBA devices found!")
		exit(1)
	if CBA.is_valid():
		voltage = CBA.get_voltage()
	else:
		print("ERROR! CBA device is not valid!")
		exit(1)
	return voltage


def main():
	if env.get("DATABASE_URL") is None:
		print("DATABASE_URL environment variable not set.")
		exit(1)
	
	try:
		os.mkdir("./results", mode=0o600)
	except FileExistsError:
		print("Directory already exists, skipping creation.")
	
	batteryNum = check()
	currentTime = datetime.now()
	date = datetime.date(currentTime)
	fullTestFileName = f"BatteryCheck-B{batteryNum}_{date.year}-{date.month}-{date.day}_{currentTime.hour}-{currentTime.minute}-{currentTime.second}"
	fullTestExportPath = f"./results/{fullTestFileName}.bt2"
	
	code = runMultipleDischargeTest([(5, 0), (5, 1)], 11.5, fullTestExportPath, getVoltageFromCba(), fullTestFileName)
	
	match code:
		case 0:
			print("Test successful. Beginning data parsing...")
		case _:
			print(f"Test failed! Error code {code}")
	
	with open(fullTestExportPath, "r", encoding='utf-8-sig') as f:
		data = ElementTree.fromstring(f.read())
		f.close()
		
	test = data.find('.//Test[@Name="Test_1"]')
	if not test:
		print("Test failed! Variable test was not defined in the file.")
		exit(1)
	
	test.find('.//TestType')
	parsedData = []
	samples = test.find('Samples')
	if not samples:
		print("Test failed! Variable samples was not defined in the file.")
		exit(1)
	
	parsedData.append({
		"date": {
			date.year,
			date.month,
			date.day
		},
		"time": {
			currentTime.hour,
			currentTime.minute,
			currentTime.second
		},
		"batteryNumber": batteryNum,
	})
	
	for sample in samples:
		sampleTime = sample.get("T")
		sampleVoltage = sample.get("V")
		sampleCurrent = sample.get("C")
		if not sampleTime or not sampleVoltage or not sampleCurrent:
			print("Test failed! Variables from samples were not defined in the file.")
			exit(1)
		parsedData.append({
			"time": int(sampleTime),
			"voltage": float(sampleVoltage),
			"current": float(sampleCurrent),
		})
	
	# will go at the end for finalizing data
	dataToServer = json.dumps(parsedData)
	
	# requests.post(os.environ.get('DATABASE_URL'), json=dataToServer)
	
	# only here right now to ensure exported data is good
	with open('./results/results.json', 'w', encoding='utf-8') as f:
		f.write(dataToServer)


if __name__ == "__main__":
	main()
