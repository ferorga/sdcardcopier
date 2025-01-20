import os
import subprocess

class SDCardMonitor:
    def __init__(self, label):
        """
        Initialize the SDCardMonitor with the label of the SD card to monitor.

        Args:
            label (str): The label of the SD card to monitor.
        """
        self.label = label
        self.device = None
        self.was_plugged = False

        self.status = "UNMOUNTED"

    def get_status(self):
        return self.status

    def get_sdcard_info(self):
        """
        Retrieve the current list of devices and their labels.

        Returns:
            dict: A dictionary where keys are labels and values are device names.
        """
        result = subprocess.run(['lsblk', '-o', 'NAME,LABEL'], capture_output=True, text=True)
        devices = {}
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                device, label = parts[0], parts[1]
                clean_device = device.split('1')[0].strip(' └─')
                devices[label] = clean_device
        return devices

    def check_plug_status(self):
        """
        Continuously monitor the SD card status and invoke a callback on change.

        Args:
            callback (function): A function to call when the SD card is plugged or unplugged.
        """
        devices = self.get_sdcard_info()
        if self.label in devices:
            self.device = devices[self.label]
            return True

        return False

    def mount(self, mount_path):
        """
        Attempt to mount the SD card.

        Args:
            mount_path (str): The path where the SD card should be mounted.

        Returns:
            bool: True if the mount was successful, False otherwise.
        """

        if self.status == "MOUNTED":
            print("Already mounted")
            return True

        partition = f"/dev/{self.device}1"
        os.makedirs(mount_path, exist_ok=True)
        result = subprocess.run(['sudo', 'mount', partition, mount_path], capture_output=True, text=True)

        if result.returncode == 0:
            print(f"Mounted {partition} to {mount_path}.")
            self.status = "MOUNTED"
            return True
        elif "already mounted" in result.stderr:
            print(f"{partition} is already mounted. Treating it as mounted.")
            self.status = "MOUNTED"
            return True
        else:
            print(f"Failed to mount {partition} to {mount_path}: {result.stderr.strip()}")
            return False

    def unmount(self):
        """
        Attempt to unmount the SD card.

        Returns:
            bool: True if the unmount was successful, False otherwise.
        """
        if self.status == "UNMOUNTED":
            print("Already unmounted")
            return True

        subprocess.run(['sudo', 'smbcontrol', 'smbd', 'close-share', 'sdcard'], capture_output=False, text=True)

        partition = f"/dev/{self.device}1"
        result = subprocess.run(['sudo', 'umount', partition], capture_output=True, text=True)

        if result.returncode == 0:
            print(f"Unmounted {partition}.")
            self.status = "UNMOUNTED"
            return True
        elif "not mounted" in result.stderr:
            print("Already unmounted")
            self.status = "UNMOUNTED"
            return True
        else:
            print(f"Failed to unmount {partition}: {result.stderr.strip()}")
            return False
