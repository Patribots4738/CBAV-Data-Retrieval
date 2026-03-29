import json
import os
import shutil
import xml.etree.ElementTree as ElementTree
from datetime import datetime
from pathlib import Path
from subprocess import run
from typing import cast

from requests import post
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
		title: str,
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
		title: str,
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


def calculateBatteryCharge(
		voltage: float
) -> float:
	# This equation was calculated by using our saved data points from the Battery Beak with around 100 data points.
	# I had Gemini do this for me since I'm barely in IM2
	# R^2 is 0.9966, so very accurate
	
	return 78.56 * voltage - 921.52


def calculateInternalResistance(
		parsedData: object,
		minCurrentChange: float = 0.1,
		maxStepSeconds: int = 15,
		cbaOffsetOhms: float = 0.0,
		highCurrentFraction: float = 0.8,
		lowCurrentFraction: float = 0.2,
) -> float:
	"""Estimate internal resistance (ohms) from parsed sample data.

	Primary method uses a step-test style plateau comparison:
	R = (V_low - V_high) / (I_high - I_low)

	Accepted input shapes include:
	- A dict like parsedData where sample dicts are values
	- A list/tuple of sample dicts

	Each sample dict must contain numeric-compatible keys: time, voltage, current.
	"""
	if parsedData is None:
		raise ValueError("parsedData cannot be None.")
	if not 0 < highCurrentFraction <= 1:
		raise ValueError("highCurrentFraction must be in the range [0, 1].")
	if not 0 <= lowCurrentFraction < 1:
		raise ValueError("lowCurrentFraction must be in the range [0, 1].")
	if lowCurrentFraction >= highCurrentFraction:
		raise ValueError("lowCurrentFraction must be less than highCurrentFraction.")

	points: list[tuple[float, float, float]] = []
	
	# noinspection PyUnnecessaryCast
	def add_point(sample: object) -> None:
		if not isinstance(sample, dict):
			return
		sample_dict = cast(dict[str, object], sample)
		raw_time = sample_dict.get("time")
		raw_voltage = sample_dict.get("voltage")
		raw_current = sample_dict.get("current")
		if raw_time is None or raw_voltage is None or raw_current is None:
			return
		if not isinstance(raw_time, (int, float, str)):
			return
		if not isinstance(raw_voltage, (int, float, str)):
			return
		if not isinstance(raw_current, (int, float, str)):
			return
		try:
			t = float(raw_time)
			v = float(raw_voltage)
			c = float(raw_current)
		except (TypeError, ValueError):
			return
		points.append((t, v, c))

	if isinstance(parsedData, dict):
		for value in parsedData.values():
			add_point(value)
	elif isinstance(parsedData, (list, tuple)):
		for value in parsedData:
			add_point(value)
	else:
		raise ValueError("parsedData must be a dict, list, or tuple containing sample dicts.")

	if len(points) < 2:
		raise ValueError("Need at least two valid samples with time, voltage, and current.")

	points.sort(key=lambda item: item[0])
	currents = [current for _, _, current in points]
	min_current = min(currents)
	max_current = max(currents)
	current_span = max_current - min_current

	if current_span < minCurrentChange:
		raise ValueError("Cannot calculate internal resistance because current does not change enough.")

	low_threshold = min_current + (current_span * lowCurrentFraction)
	high_threshold = min_current + (current_span * highCurrentFraction)

	first_high_index = None
	for index, (_, _, current) in enumerate(points):
		if current >= high_threshold:
			first_high_index = index
			break

	if first_high_index is None:
		raise ValueError("Could not find a high-current step in parsedData.")
	first_high_time = points[first_high_index][0]

	low_points = [
		(voltage, current)
		for t, voltage, current in points[:first_high_index + 1]
		if current <= low_threshold and (first_high_time - t) <= maxStepSeconds
	]

	high_points: list[tuple[float, float]] = []
	for t, voltage, current in points[first_high_index:]:
		if (t - first_high_time) > maxStepSeconds and high_points:
			break
		if current >= high_threshold:
			high_points.append((voltage, current))
		elif high_points:
			# Stop after the first high-current plateau to avoid rebound skew.
			break

	if not low_points or not high_points:
		raise ValueError("Insufficient low/high plateau points to calculate internal resistance.")

	low_voltage = sum(voltage for voltage, _ in low_points) / len(low_points)
	low_current = sum(current for _, current in low_points) / len(low_points)
	high_voltage = sum(voltage for voltage, _ in high_points) / len(high_points)
	high_current = sum(current for _, current in high_points) / len(high_points)

	delta_current = high_current - low_current
	if delta_current <= 0 or abs(delta_current) < minCurrentChange:
		raise ValueError("Current step is too small to calculate internal resistance.")

	raw_resistance = abs((low_voltage - high_voltage) / delta_current)
	corrected_resistance = max(0.0, raw_resistance - cbaOffsetOhms)

	return round(corrected_resistance, 4)


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
	
	code = runMultipleDischargeTest([(3, 1), (3, 10)], 11.5, fullTestTestPath, fullTestFileName)
	
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
	if test is None:
		print("Test failed! Variable test was not defined in the file.")
		exit(1)
	
	parsedData = {}
	samples = test.find('Samples')
	if samples is None:
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
		"initialVoltage": calculateBatteryCharge(voltageData[1]),
	}
	parsedData["datapoints"] = {}
	currentSample = 0
	
	for sample in samples:
		sampleTime = sample.get("T")
		sampleVoltage = sample.get("V")
		sampleCurrent = sample.get("C")
		if not sampleTime or not sampleVoltage or not sampleCurrent:
			print("Test failed! Variables from samples were not defined in the file.")
			exit(1)
		
		# We have an external variable outside the loop to be used for calculating the internal resistance of the battery
		parsedData["datapoints"][currentSample] = {
			"time": int(sampleTime),
			"voltage": float(sampleVoltage),
			"current": float(sampleCurrent),
		}
	
		currentSample += 1
	
	cbaOffset = env.get("CBA_OFFSET_OHMS")
	if cbaOffset is None:
		print("Test failed! CBA_OFFSET_OHMS environment variable not set.")
		exit(1)
	cbaOffset = float(cbaOffset)
	
	try:
		internalResistanceCorrected = calculateInternalResistance(parsedData, cbaOffsetOhms=cbaOffset)
	except ValueError as e:
		print("Test failed! Could not calculate internal resistance from parsed data.")
		print(f"Error {e}")
		exit(1)
	
	parsedData["header"]["internalResistance"] = internalResistanceCorrected
	
	jsonData = json.dumps(parsedData)
	
	post(os.environ.get('DATABASE_URL'), json=jsonData)


if __name__ == "__main__":
	main()
