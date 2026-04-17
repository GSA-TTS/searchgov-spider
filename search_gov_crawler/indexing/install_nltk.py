from concurrent.futures import ThreadPoolExecutor

import nltk


def download_nltk_package(package) -> str:
    """Download a single NLTK package."""
    try:
        nltk.download(info_or_id=package, quiet=True)
    except Exception as e:
        return f"Failed to download {package}: {e!s}"

    return f"Successfully downloaded {package}"


nltk_packages = ["popular", "punkt_tab", "punkt", "perluniprops", "nonbreaking_prefixes", "stopwords"]

with ThreadPoolExecutor(max_workers=len(nltk_packages)) as executor:
    future_to_package = {executor.submit(download_nltk_package, package): package for package in nltk_packages}

    for future in future_to_package:  # noqa: PLC0206
        package = future_to_package[future]
        try:
            result = future.result()
            print(result)
        except Exception as e:
            print(f"Error downloading {package}: {e!s}")
