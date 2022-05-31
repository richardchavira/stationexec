#define PY_SSIZE_T_CLEAN
// Uncomment this line to build the "w" variant that does not show the console window
//#pragma comment(linker, "/SUBSYSTEM:windows /ENTRY:mainCRTStartup")

#include <fstream>
#include <string>

#include <KnownFolders.h>
#include <ShlObj.h>
#include <windows.h>

#define PYTHON_VERSION_LOCATION 34
#define PYTHON_LONG_VERSION_LOCATION 35
#define MAIN_FILE_NAME_LOCATION 36
#define MAIN_FILE_DATA_LOCATION 37
#define LIB_NAME_LOCATION 38
#define LIB_FILE_LOCATION 39
#define PROGRAM_NAME_LOCATION 42
#define PROGRAM_FILE_LOCATION 43
#define PY_RESOURCE_HASH_NAME_LOCATION 46
#define PY_RESOURCE_HASH_LOCATION 47
#define PY_RESOURCE_ZIP_NAME_LOCATION 48
#define PY_RESOURCE_ZIP_LOCATION 49
#define PY_RESOURCE_COUNT_LOCATION 50
#define PY_RESOURCE_FILES_START_LOCATION 51
#define PY_RESOURCE_NAMES_START_LOCATION 151

typedef int(__cdecl* PYFUNCW)(LPWSTR);
typedef int(__cdecl* PYMAIN)(int, wchar_t**);

void print_last_error_message(void) {
  LPWSTR buffer;
  DWORD message_length;
  DWORD error_number = GetLastError();

  DWORD dwFormatFlags =
      FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_IGNORE_INSERTS | FORMAT_MESSAGE_FROM_SYSTEM;

  message_length = FormatMessage(
      dwFormatFlags,
      NULL, // module to get message from (NULL == system)
      error_number,
      MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT), // default language
      (LPSTR)&buffer,
      0,
      NULL);
  if (message_length) {
    // Output message
    fprintf(stdout, "Windows error message (Error %d):\n%ls\n", error_number, buffer);
    // Free the buffer allocated by the system.
    LocalFree(buffer);
  }
}

bool check_if_directory_exists(char* path) {
  DWORD dwAttrib = GetFileAttributes(path);
  return (dwAttrib != INVALID_FILE_ATTRIBUTES && (dwAttrib & FILE_ATTRIBUTE_DIRECTORY));
}

bool check_if_file_exists(char* path) {
  DWORD dwAttrib = GetFileAttributes(path);
  return (dwAttrib != INVALID_FILE_ATTRIBUTES && !(dwAttrib & FILE_ATTRIBUTE_DIRECTORY));
}

void create_and_write_file_from_res(
    int name_res_number,
    int file_res_number,
    char* path,
    bool delete_existing) {
  HANDLE g_hFile;
  DWORD cbWritten;
  char pyFileName[_MAX_PATH];
  char pyFilePath[_MAX_PATH];

  HRSRC pyResource = FindResource(NULL, MAKEINTRESOURCE(file_res_number), RT_RCDATA);
  unsigned long pyResourceSize = SizeofResource(NULL, pyResource);
  HGLOBAL pyResourcePointer = LoadResource(NULL, pyResource);
  char* pyResourcePtr = (char*)LockResource(pyResourcePointer);

  HRSRC pyResourceName = FindResource(NULL, MAKEINTRESOURCE(name_res_number), RT_RCDATA);
  unsigned long pyResourceNameSize = SizeofResource(NULL, pyResourceName);
  HGLOBAL pyResourceNamePointer = LoadResource(NULL, pyResourceName);
  char* pyResourceNamePtr = (char*)LockResource(pyResourceNamePointer);

  _snprintf_s(pyFileName, (size_t)256, (size_t)pyResourceNameSize, pyResourceNamePtr);
  _snprintf_s(pyFilePath, (size_t)_MAX_PATH, "%s\\%s", path, pyFileName);

  if (check_if_file_exists(pyFilePath)) {
    if (delete_existing)
      DeleteFileA(pyFilePath);
  }

  g_hFile = CreateFile(
      pyFilePath, // name of file
      GENERIC_WRITE, // access mode
      0, // share mode
      (LPSECURITY_ATTRIBUTES)NULL, // default security
      CREATE_ALWAYS, // create flags
      FILE_ATTRIBUTE_NORMAL, // file attributes
      (HANDLE)NULL); // no template

  WriteFile(
      g_hFile, // file to hold resource info
      pyResourcePtr, // what to write to the file
      (DWORD)pyResourceSize, // number of bytes in szBuffer
      &cbWritten, // number of bytes written
      NULL); // no overlapped I/O

  CloseHandle(g_hFile);

  // fprintf(stdout, "File: %s Size: %lu Size Written: %lu\n", pyFilePath, pyResourceSize,
  // cbWritten);
}

void delete_folder_if_exists(char* path) {
  // Requires double null terminated path string to function
  SHFILEOPSTRUCTA lpFileOp;
  if (check_if_directory_exists(path)) {
    lpFileOp.wFunc = FO_DELETE;
    lpFileOp.pFrom = path;
    lpFileOp.fFlags = FOF_NO_UI;
    int ret = SHFileOperation(&lpFileOp);
  }
}

int main(int argc, char* argv[]) {
  PYMAIN pymain;
  PYFUNCW pysethome;
  PYFUNCW pysetpath;

  PWSTR appPath = NULL;
  char basePath[_MAX_PATH];
  char pythonHome[_MAX_PATH];
  char pythonDLL[_MAX_PATH];
  char pyVersionName[256];
  char pyVersionNameLong[256];

  // Get the version string for python (like 'python36')
  HRSRC pyVersion = FindResource(NULL, MAKEINTRESOURCE(PYTHON_VERSION_LOCATION), RT_RCDATA);
  unsigned long pyVersionSize = SizeofResource(NULL, pyVersion);
  HGLOBAL pyVersionPointer = LoadResource(NULL, pyVersion);
  char* pyResourceNamePtr = (char*)LockResource(pyVersionPointer);
  _snprintf_s(pyVersionName, (size_t)256, (size_t)pyVersionSize, pyResourceNamePtr);

  // Get the long version string for python (like 'python363_64')
  HRSRC pyVersionLong =
      FindResource(NULL, MAKEINTRESOURCE(PYTHON_LONG_VERSION_LOCATION), RT_RCDATA);
  unsigned long pyVersionSizeLong = SizeofResource(NULL, pyVersionLong);
  HGLOBAL pyVersionPointerLong = LoadResource(NULL, pyVersionLong);
  char* pyResourceNamePtrLong = (char*)LockResource(pyVersionPointerLong);
  _snprintf_s(pyVersionNameLong, (size_t)256, (size_t)pyVersionSizeLong, pyResourceNamePtrLong);

  // Get Paths to installation directory with folders for python and python libs
  HRESULT res = SHGetKnownFolderPath(FOLDERID_LocalAppData, 0, NULL, &appPath);
  _snprintf_s(basePath, (size_t)_MAX_PATH, "%ls\\stationexec", appPath);
  _snprintf_s(pythonHome, (size_t)_MAX_PATH, "%ls\\stationexec\\%s", appPath, pyVersionNameLong);
  CoTaskMemFree(appPath);

  if (!check_if_directory_exists(basePath))
    CreateDirectory(basePath, NULL);

  if (!check_if_directory_exists(pythonHome))
    CreateDirectory(pythonHome, NULL);

  // If the active version of python is not already installed, do so now
  HRSRC rscCount = FindResource(NULL, MAKEINTRESOURCE(PY_RESOURCE_COUNT_LOCATION), RT_RCDATA);
  HGLOBAL rscCountPointer = LoadResource(NULL, rscCount);
  unsigned char* countPtr = (unsigned char*)LockResource(rscCountPointer);
  unsigned char count = countPtr[0];

  for (int i = 0; i < count; i++) {
    create_and_write_file_from_res(
        PY_RESOURCE_NAMES_START_LOCATION + i,
        PY_RESOURCE_FILES_START_LOCATION + i,
        pythonHome,
        FALSE);
  }

  // Write launcher script
  create_and_write_file_from_res(MAIN_FILE_NAME_LOCATION, MAIN_FILE_DATA_LOCATION, basePath, TRUE);

  // Copy required Python libraries zip
  create_and_write_file_from_res(LIB_NAME_LOCATION, LIB_FILE_LOCATION, basePath, TRUE);

  // Copy program zip and hash file
  create_and_write_file_from_res(PROGRAM_NAME_LOCATION, PROGRAM_FILE_LOCATION, basePath, TRUE);

  // Copy python zip and hash file
  create_and_write_file_from_res(
      PY_RESOURCE_ZIP_NAME_LOCATION, PY_RESOURCE_ZIP_LOCATION, basePath, TRUE);
  create_and_write_file_from_res(
      PY_RESOURCE_HASH_NAME_LOCATION, PY_RESOURCE_HASH_LOCATION, basePath, TRUE);

  // ------------------------------------------------------

  _snprintf_s(pythonDLL, (size_t)_MAX_PATH, "%s\\%s.dll", pythonHome, pyVersionName);
  HMODULE dll = LoadLibrary(pythonDLL);
  if (dll == NULL) {
    print_last_error_message();
  }

  pymain = (PYMAIN)GetProcAddress(dll, "Py_Main");
  pysethome = (PYFUNCW)GetProcAddress(dll, "Py_SetPythonHome");
  pysetpath = (PYFUNCW)GetProcAddress(dll, "Py_SetPath");

  wchar_t paths[32768];
  _snwprintf_s(paths, 32768, L"%S\\%S", basePath, pyVersionNameLong);
  pysethome(paths);
  _snwprintf_s(
      paths,
      32768,
      L"%S;"
      "%S\\%S;"
      "%S\\%S\\%S.zip;"
      "%S\\lib.zip",
      basePath,
      basePath,
      pyVersionNameLong,
      basePath,
      pyVersionNameLong,
      pyVersionName,
      basePath);
  pysetpath(paths);

  wchar_t clargs[32][_MAX_PATH];
  const wchar_t* args[32];
  args[0] = L"";
  args[1] = L"-I";
  _snwprintf_s(paths, _MAX_PATH, L"%S\\%S", basePath, "launch.py");
  args[2] = paths;

  for (int i = 1; i < argc; i++) {
    _snwprintf_s(clargs[i], _MAX_PATH, L"%S", argv[i]);
    args[2 + i] = clargs[i];
  }

  pymain(3 + (argc - 1), (wchar_t**)args);

  // Uncomment and run this instead to go into REPL
  // pymain(1, (wchar_t **)args);

  FreeLibrary(dll);
}
