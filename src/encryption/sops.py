import json
import os
import subprocess
import tempfile
from contextlib import contextmanager


def assert_file_exists(filepath):
    """Assert a filepath exists, raise an error if not. This function is to be used for
    files that *absolutely have to exist* in order to successfully run the code, such
    as, encrypted secret files

    Args:
        filepath (str): Absolute path to the file that is to be asserted for existence
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found at following location: {filepath}")


@contextmanager
def get_decrypted_file(original_filepath):
    """
    Assert that a given file exists. If the file is sops-encryped, we provide secure,
    temporarily decrypted contents of the file. We raise an error if we do not find the
    sops key when we expect to, in case the decrypted contents have been leaked via
    version control. We expect to find the sops key in a file if the filepath contains
    the word "secrets". If the file is not encrypted, we return the original filepath.

    Args:
        original_filepath (path object): Absolute path to a file to perform checks on
            and decrypt if it's encrypted

    Yields:
        (path object): EITHER the absolute path to a tempfile containing the
            decrypted contents, OR the original filepath. The original filepath is
            yielded if the file is not valid JSON, or does not contain 'secrets'.
    """
    assert_file_exists(original_filepath)

    # First check for "secrets" in the filepath
    if "secrets" in str(original_filepath):
        # Then check the file is valid JSON
        with open(original_filepath) as f:
            try:
                content = json.load(f)
            except json.JSONDecodeError:
                raise json.JSONDecodeError(
                    "We expect encrypted files to be valid JSON files.", "", 0
                )

        # Now check for the `sops` key, indicating that it is encrypted
        if "sops" not in content:
            raise KeyError(
                "Expecting to find the `sops` key in this encrypted file - but it "
                + "wasn't found! Please regenerate the secret in case it has been "
                + f"checked into version control and leaked!\n{original_filepath}"
            )

        # Decrypt the file contents with sops into a temp file
        with tempfile.NamedTemporaryFile() as f:
            subprocess.check_call(
                ["sops", "--output", f.name, "--decrypt", original_filepath]
            )
            yield f.name

    else:
        # This file does not have "secrets" in it's name, therefore does not need to be
        # decrypted. Yield the original filepath unchanged.
        yield original_filepath
