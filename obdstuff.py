import serial
import time
import serial.tools.list_ports
import threading

def hex_to_decimal(hex_str):
    return int(hex_str, 16)

def parse_speed(response):
    try:
        response = response.strip().replace("\r", "").replace("\n", "")
        parts = response.split()
        if len(parts) >= 3 and parts[1] == '0D':
            speed_hex = parts[2]
            speed = hex_to_decimal(speed_hex)
            return f"{speed} km/h"
        else:
            return "No speed data."
    except Exception as e:
        return f"Error parsing speed: {e}"

def parse_rpm(response):
    try:
        response = response.strip().replace("\r", "").replace("\n", "")
        parts = response.split()
        if len(parts) >= 4 and parts[1] == '0C':
            A = hex_to_decimal(parts[2])
            B = hex_to_decimal(parts[3])
            rpm = ((A * 256) + B) / 4
            return f"{rpm} RPM"
        else:
            return "No RPM data."
    except Exception as e:
        return f"Error parsing RPM: {e}"

def send_command(ser, command):
    ser.write(f"{command}\r".encode())
    time.sleep(1)
    response = ser.read_all().decode('utf-8', errors='ignore').strip()
    return response

def test_port(port, baud_rate, timeout, result, stop_event):
    if stop_event.is_set():
        return

    try:
        ser = serial.Serial(port.device, baud_rate, timeout=timeout)
        print(f"Testing port: {port.device}")

        # Test connection with 'ATZ' command
        ser.write(b'ATZ\r')
        time.sleep(1)
        response = ser.read_all().decode('utf-8', errors='ignore').strip()
        if response and not stop_event.is_set():
            print(f"OBD-II adapter found on port: {port.device}")
            result["found"] = port.device
            stop_event.set()  # Signal other threads to stop
        ser.close()
    except Exception as e:
        print(f"Failed to connect on port {port.device}: {e}")

def find_obd_port_multithreaded(baud_rate=9600, timeout=1):
    ports = serial.tools.list_ports.comports()
    threads = []
    result = {"found": None}
    stop_event = threading.Event()

    for port in ports:
        thread = threading.Thread(target=test_port, args=(port, baud_rate, timeout, result, stop_event))
        threads.append(thread)
        thread.start()

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

    return result["found"]

def main():
    baud_rate = 9600  # Standard OBD-II baud rate
    obd_port = find_obd_port_multithreaded(baud_rate)

    if obd_port is None:
        print("No OBD-II adapter found.")
        return

    try:
        ser = serial.Serial(obd_port, baud_rate, timeout=1)
        print(f"Opened serial port: {obd_port} at {baud_rate} baud.")
        time.sleep(2)  # Allow time for the adapter to initialize

        # Reset the adapter
        response = send_command(ser, 'ATZ')
        print(f"Response to 'ATZ': {response}")

        # Set protocol to automatic
        response = send_command(ser, 'ATSP0')
        print(f"Response to 'ATSP0': {response}")

        # Test multiple PIDs
        pids = ['010C', '010D', '0105']  # RPM, Speed, Coolant Temp
        for pid in pids:
            response = send_command(ser, pid)
            print(f"Raw Response to '{pid}': {response}")
            if pid == '010D':  # Vehicle Speed
                speed = parse_speed(response)
                print(f"Parsed Vehicle Speed: {speed}")
            elif pid == '010C':  # Engine RPM
                rpm = parse_rpm(response)
                print(f"Parsed Engine RPM: {rpm}")

        ser.close()
        print("Closed serial port.")
    
    except serial.SerialException as e:
        print(f"Serial exception: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
