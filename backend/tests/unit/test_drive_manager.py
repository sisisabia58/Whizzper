from modules.utils.drive_manager import parse_folder_id

def test_parse_folder_id():
    url = "https://drive.google.com/drive/folders/1A2B3C-4D5E6F_7G8H9I?usp=sharing"
    assert parse_folder_id(url) == "1A2B3C-4D5E6F_7G8H9I"

    url2 = "https://drive.google.com/open?id=1A2B3C-4D5E6F_7G8H9I"
    # Open URL isn't a direct folders/ ID, but let's test a non-folders URL returns None
    assert parse_folder_id(url2) is None
