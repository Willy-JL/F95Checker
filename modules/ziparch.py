# https://gist.github.com/Willy-JL/9e3e6fac4fdbdb3d40fccdb329fe32f1
import os
import pathlib
import zipfile

ZIP_COMPRESS_TYPE = zipfile.ZIP_DEFLATED

ZIP_ARCH_EXTENSION = ".zip"


def zip_sanitizer_filter(zipinfo: zipfile.ZipInfo):
    zipinfo.date_time = (1980, 1, 1, 0, 0, 0)  # Minimum date
    if zipinfo.is_dir():
        zipinfo.external_attr = 0o40775 << 16  # drwxr-xr-x
        zipinfo.external_attr |= 0x10          # MS-DOS directory flag
    else:
        zipinfo.external_attr = 0o644 << 16    # ?rw-r--r--
    zipinfo.create_system = 0  # Unix-like
    return zipinfo


def compress_tree_ziparch(
    src_dir,
    output_name,
    filter=zip_sanitizer_filter,
    gz_level=9,
):
    top = pathlib.Path(src_dir)
    original_size = 0

    with zipfile.ZipFile(
        file=output_name,
        mode="w",
        compression=ZIP_COMPRESS_TYPE,
        compresslevel=gz_level,
    ) as ziparch:
        for cur, dirs, files in os.walk(top):
            cur = pathlib.Path(cur)
            dirs.sort()
            files.sort()

            if cur != top:
                zipinfo = zipfile.ZipInfo.from_file(cur, cur.relative_to(top))
                zipinfo.compress_size = 0
                zipinfo.CRC = 0
                ziparch.mkdir(filter(zipinfo))

            for file in files:
                path = cur / file
                original_size += top.stat().st_size
                zipinfo = zipfile.ZipInfo.from_file(path, path.relative_to(top))
                ziparch.writestr(
                    filter(zipinfo),
                    path.read_bytes(),
                    compress_type=ZIP_COMPRESS_TYPE,
                    compresslevel=gz_level,
                )

    return original_size, os.stat(output_name).st_size
