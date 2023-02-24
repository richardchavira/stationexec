import subprocess
import sys
import re

def get_installed_library_versions() -> dict:
        try:
            output = subprocess.check_output([sys.executable, "-m", "pip", "list"], encoding='UTF-8')
        except subprocess.CalledProcessError as e:
            print(e.output)

        library_pattern = r'(.\S+) +([0-9.]+)'
        output_lines = output.split('\n')
        installed_libraries = {}
        
        for line in output_lines:
            # check if line contains a library / version
            match = re.findall(string=line, pattern=library_pattern, flags=re.IGNORECASE)
            if match:
                library_name = match[0][0]
                version = match[0][1]
                installed_libraries[library_name] = version

        return installed_libraries