import json
import os
import sys
import xml.etree.ElementTree as ElementTree
from datetime import datetime
from pathlib import Path
from subprocess import run

import requests
from dotenv import load_dotenv


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
		title: str = "Test",
) -> int:
	n = len(points)
	point_str = ",".join(f"{t},{a}" for t, a in points)
	multiple_arg = f"{n},{point_str}"
	
	WMRCBA = "C:\\Program Files (x86)\\West Mountain Radio\\CBA Software V3\\WMRCBA.exe"
	if not Path(WMRCBA).is_file():
		print("ERROR! CBA Software may not be installed!")
		exit(1)
	
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
	]
	
	result = run(cmd)
	
	return result.returncode


def main():
	
	load_dotenv()
	if os.environ.get("DATABASE_URL") is None:
		print("DATABASE_URL environment variable not set.")
		exit(1)
	
	try:
		os.mkdir("results", mode=0o600)
	except FileExistsError:
		print("Directory already exists, skipping creation.")
	
	num = check()
	currentTime = datetime.now()
	date = datetime.date(currentTime)
	fullTestFileName = f"BatteryCheck-B{num}_{date.year}-{date.month}-{date.day}_{currentTime.hour}-{currentTime.minute}-{currentTime.second}"
	fullTestExportPath = f"./results/{fullTestFileName}.bt2"
	
	code = runMultipleDischargeTest([(5, 0), (5, 1)], 11.5, fullTestExportPath, fullTestFileName)
	
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
	
	requests.post(os.environ.get('DATABASE_URL'), json=parsedData)
	
	# will go at the end for finalizing data
	dataToServer = json.dumps(parsedData)
	
	# only here right not to ensure exported data is good
	with open('results.json', 'w', encoding='utf-8') as f:
		f.write(dataToServer)


if __name__ == "__main__":
	main()
