#include <windows.h>
#include <string>

#include "resource.h"

#pragma pack(push)
#pragma pack(2)
typedef struct {
  BYTE bWidth; // Width, in pixels, of the image
  BYTE bHeight; // Height, in pixels, of the image
  BYTE bColorCount; // Number of colors in image (0 if >=8bpp)
  BYTE bReserved; // Reserved
  WORD wPlanes; // Color Planes
  WORD wBitCount; // Bits per pixel
  DWORD dwBytesInRes; // how many bytes in this resource?
  WORD nID; // the ID
} GRPICONDIRENTRY, *LPGRPICONDIRENTRY;
#pragma pack(pop)

#pragma pack(push)
#pragma pack(2)
typedef struct {
  WORD idReserved; // Reserved (must be 0)
  WORD idType; // Resource type (1 for icons)
  WORD idCount; // How many images?
  GRPICONDIRENTRY idEntries[1]; // The entries for each image
} GRPICONDIR, *LPGRPICONDIR;
#pragma pack(pop)

int main(int argc, char* argv[]) {
  HANDLE hUpdateRes;
  BOOL result;
  HANDLE hFile;
  DWORD fileSize;
  DWORD bytesRead;
  BYTE* buffer;

  char drive[_MAX_DRIVE];
  char dir[_MAX_DIR];
  char fname[_MAX_FNAME];
  char ext[_MAX_EXT];

  char targetFile[_MAX_PATH];
  char outZip[_MAX_PATH];
  char basePath[_MAX_PATH];

  _snprintf_s(targetFile, (size_t)_MAX_PATH, "py.zip");
  _snprintf_s(outZip, (size_t)_MAX_PATH, "out.zip");
  _snprintf_s(basePath, (size_t)_MAX_PATH, "");

  int iconChoice = IDI_STANDARD;
  if (!strcmp(argv[1], "debug"))
    iconChoice = IDI_DEBUG;

  HRSRC pyIconGroupRes = FindResource(NULL, MAKEINTRESOURCE(iconChoice), RT_GROUP_ICON);
  unsigned long pyIconGroupSize = SizeofResource(NULL, pyIconGroupRes);
  HGLOBAL pyIconGroupPointer = LoadResource(NULL, pyIconGroupRes);
  GRPICONDIR* pyIconGroup = (GRPICONDIR*)LockResource(pyIconGroupPointer);

  hUpdateRes = BeginUpdateResource(argv[2], FALSE);

  result = UpdateResource(
      hUpdateRes,
      RT_GROUP_ICON,
      MAKEINTRESOURCE(101),
      MAKELANGID(LANG_NEUTRAL, SUBLANG_NEUTRAL),
      pyIconGroup,
      pyIconGroupSize);

  for (int i = 0; i < pyIconGroup->idCount; i++) {
    HRSRC pyIconRes = FindResource(NULL, MAKEINTRESOURCE(pyIconGroup->idEntries[i].nID), RT_ICON);
    unsigned long pyIconSize = SizeofResource(NULL, pyIconRes);
    HGLOBAL pyIconPointer = LoadResource(NULL, pyIconRes);
    GRPICONDIRENTRY* pyIcon = (GRPICONDIRENTRY*)LockResource(pyIconPointer);

    result = UpdateResource(
        hUpdateRes,
        RT_ICON,
        MAKEINTRESOURCE(pyIconGroup->idEntries[i].nID),
        MAKELANGID(LANG_NEUTRAL, SUBLANG_NEUTRAL),
        pyIcon,
        pyIconSize);
  }

  for (int i = 3; i < argc; i++) {
    hFile = CreateFile(
        argv[i], // name of file
        GENERIC_READ, // access mode
        FILE_SHARE_READ, // share mode
        NULL, // default security
        OPEN_EXISTING, // create flags
        FILE_ATTRIBUTE_NORMAL, // file attributes
        NULL); // no template

    fileSize = GetFileSize(hFile, NULL);
    buffer = new BYTE[fileSize];
    ReadFile(hFile, buffer, fileSize, &bytesRead, NULL);

    _splitpath_s(argv[i], drive, _MAX_DRIVE, dir, _MAX_DIR, fname, _MAX_FNAME, ext, _MAX_EXT);

    result = UpdateResource(
        hUpdateRes,
        RT_RCDATA,
        MAKEINTRESOURCE(atoi(fname)),
        MAKELANGID(LANG_NEUTRAL, SUBLANG_NEUTRAL),
        buffer,
        fileSize);

    delete[] buffer;
    CloseHandle(hFile);
  }

  EndUpdateResource(hUpdateRes, FALSE);
}
