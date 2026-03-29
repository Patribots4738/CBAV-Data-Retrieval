import json
import os
import shutil
import xml.etree.ElementTree as ElementTree
from datetime import datetime
from pathlib import Path
from subprocess import run

from dotenv import load_dotenv

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
			

def getVoltageFromCba(
		output_path: str,
		title: str = "Test",
) -> list[float]:
	WMRCBA = "C:\\Program Files (x86)\\West Mountain Radio\\CBA Software V3\\WMRCBA.exe"
	if not Path(WMRCBA).is_file():
		print("ERROR! CBA Software may not be installed!")
		exit(1)
	
	cmd = [
		WMRCBA,
		"/test",
		"multiple",
		"1,1,0",
		"/cutoff",
		"10.5",
		"/open",
		output_path,
		"/title",
		title,
	]
	
	result = run(cmd)
	
	match result.returncode:
		case 0:
			pass
		case _:
			print(f"Test failed! Error code {result}")
	
	with open(output_path, "r", encoding='utf-8-sig') as f:
		data = ElementTree.fromstring(f.read())
		f.close()
	
	test = data.find(f'.//Test[@Name="{title}"]')
	if test is None:
		print("Test failed! Variable test was not defined in the file.")
		exit(1)
	
	samples = test.find('Samples')
	if samples is None:
		print("Test failed! Variable samples was not defined in the file.")
		exit(1)
	
	voltage = 0.0
	validSamples = 0
	for i in samples:
		sampleVoltage = i.get("V")
		if sampleVoltage is None:
			pass
		else:
			voltage += float(sampleVoltage)
			validSamples += 1
	
	voltage = round(voltage / validSamples, 1)
	
	if voltage <= 0 or voltage > 14:
		print("ERROR! Invalid voltage supplied!")
		exit(1)
	
	try:
		return [result.returncode, float(voltage)]
	except ValueError as e:
		print("ERROR! Could not convert voltage to float!")
		print(f"Error {e}")
		exit(1)


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
		"/temperature",
		"125"
	]
	
	result = run(cmd)
	
	return result.returncode


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
	initialVoltageFileName = f"voltagecheck-b{batteryNum}_{date.year}-{date.month}-{date.day}_{currentTime.hour}-{currentTime.minute}-{currentTime.second}"
	initialVoltageTestPath = f"{initialVoltageFileName}.bt2"
	initialVoltageExportPath = f"./results/{initialVoltageFileName}.bt2"
	fullTestFileName = f"batterycheck-b{batteryNum}_{date.year}-{date.month}-{date.day}_{currentTime.hour}-{currentTime.minute}-{currentTime.second}"
	fullTestTestPath = f"{fullTestFileName}.bt2"
	fullTestExportPath = f"./results/{fullTestFileName}.bt2"
	
	voltageData = getVoltageFromCba(initialVoltageTestPath, initialVoltageFileName)
	if os.path.isfile(initialVoltageTestPath):
		shutil.move(initialVoltageTestPath, initialVoltageExportPath)
	if voltageData[0] != 0:
		print(f"Voltage check failed! Error code {voltageData[0]}")
		exit(1)
	
	code = runMultipleDischargeTest([(5, 0), (5, 1)], 11.5, fullTestTestPath, fullTestFileName)
	
	if os.path.isfile(fullTestTestPath):
		shutil.move(fullTestTestPath, fullTestExportPath)
	
	match code:
		case 0:
			print("Test successful. Beginning data parsing...")
		case _:
			print(f"Test failed! Error code {code}")
			exit(1)
	
	with open(fullTestExportPath, "r", encoding='utf-8-sig') as f:
		data = ElementTree.fromstring(f.read())
		f.close()
		
	test = data.find(f'.//Test[@Name="{fullTestFileName}"]')
	if not test:
		print("Test failed! Variable test was not defined in the file.")
		exit(1)
	
	parsedData = {}
	samples = test.find('Samples')
	if not samples:
		print("Test failed! Variable samples was not defined in the file.")
		exit(1)
	
	parsedData["header"] = {
		"date": {
			"year": date.year,
			"month": date.month,
			"day": date.day
		},
		"time": {
			"hour": currentTime.hour,
			"time": currentTime.minute,
			"second": currentTime.second
		},
		"batteryNumber": batteryNum,
		"initialVoltage": voltageData[1],
	}
	
	for sample in samples:
		sampleTime = sample.get("T")
		sampleVoltage = sample.get("V")
		sampleCurrent = sample.get("C")
		if not sampleTime or not sampleVoltage or not sampleCurrent:
			print("Test failed! Variables from samples were not defined in the file.")
			exit(1)
		parsedData[sample] = {
			"time": int(sampleTime),
			"voltage": float(sampleVoltage),
			"current": float(sampleCurrent),
		}
	
	# will go at the end for finalizing data, indent is purely for human readability in testing
	dataToServer = json.dumps(parsedData, indent=4)
	
	# requests.post(os.environ.get('DATABASE_URL'), json=dataToServer)
	
	# TODO: calculate internal resistance and subtract 0.04 ohms to account for CBA offset, then add to dataToServer before sending to server
	# only here right now to ensure exported data is good
	with open('./results/results.json', 'w', encoding='utf-8') as f:
		f.write(dataToServer)


if __name__ == "__main__":
	main()
