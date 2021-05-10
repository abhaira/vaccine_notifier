import smtplib
import ssl
import time
from datetime import datetime, timedelta
import requests
import logging
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

auth = dict()
base_url = "https://cdn-api.co-vin.in/api"

today = datetime.now().strftime('%d-%m-%Y')
yesterday = (datetime.now() - timedelta(1)).strftime('%d-%m-%Y')
tomorrow = (datetime.now() + timedelta(1)).strftime('%d-%m-%Y')

port = 465
smtp_server = "smtp.gmail.com"
# make sure less secure access is ON for this account
# https://myaccount.google.com/lesssecureapps
sender_email = "xyz@gmail.com"
password = "xyz"
notification_targets = ["pqr@gmail.com"]


def clear_screen():
    import os

    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


def _send_email(receiver_email, message):
    try:
        context = ssl.create_default_context()

        with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message)
            return True

    except Exception as e:
        pass
    return False


def _is_response_successful(response):
    if response is None:
        return False

    if response.status_code != 200:
        return False

    if response.text == '':
        return False

    if not hasattr(response, 'json'):
        return False

    json_data_response = response.json()

    if json_data_response is None:
        return False

    if 'error' in json_data_response and json_data_response['error'] != 0:
        return False

    return True


def generate_otp(number):
    url = base_url + "/v2/auth/public/generateOTP"
    payload = {"mobile": number}

    response = requests.post(url, json=payload, verify=False)

    if not _is_response_successful(response):
        logger.error("Could not generate OTP")
        return False

    data = response.json()
    auth["txnId"] = data["txnId"]
    return True


def confirm_otp(otp):
    url = base_url + "/v2/auth/public/confirmOTP"
    import hashlib
    otp_sha256 = hashlib.sha256(otp.encode())
    payload = {
        "otp": otp_sha256.hexdigest(),
        "txnId": auth["txnId"]
    }

    response = requests.post(url, json=payload, verify=False)

    if not _is_response_successful(response):
        logger.error("Could not confirm OTP")
        return False

    data = response.json()
    auth["token"] = data["token"]
    return True


def get_calendar(district_id):
    url = base_url + "/v2/appointment/sessions/calendarByDistrict"
    headers = {
        "authorization": f"Bearer {auth['token']}",
        "accept": "application/json",
        "accept-language": "en_US",
        "accept-encoding": "gzip, deflate, br",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36 Edg/90.0.818.51"
    }

    params = {
        "district_id": district_id,
        "date": today
    }

    rsp = requests.get(url, headers=headers, params=params, verify=False)
    if not _is_response_successful(rsp):
        logger.error("failed to get calendar")
        return None

    return rsp.json()


def get_states():
    url = base_url + "/v2/admin/location/states"
    headers = {
        "authorization": f"Bearer {auth['token']}",
        "accept": "application/json",
        "accept-language": "en_US",
        "accept-encoding": "gzip, deflate, br",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36 Edg/90.0.818.51"
    }

    rsp = requests.get(url, headers=headers, verify=False)
    if not _is_response_successful(rsp):
        logger.error("failed to get calendar")
        return None

    states_json = rsp.json()

    return states_json['states']


def print_states(states):
    for index in range(len(states)):
        print(f"\t{index} -> {states[index]['state_name']}")


def get_districts(state_id):
    url = base_url + f"/v2/admin/location/districts/{state_id}"
    headers = {
        "authorization": f"Bearer {auth['token']}",
        "accept": "application/json",
        "accept-language": "en_US",
        "accept-encoding": "gzip, deflate, br",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36 Edg/90.0.818.51"
    }
    params = {
        "state_id": state_id
    }

    rsp = requests.get(url, headers=headers, params=params, verify=False)
    if not _is_response_successful(rsp):
        logger.error("failed to get calendar")
        return None

    districts_json = rsp.json()

    return districts_json['districts']


def print_districts(districts):
    for index in range(len(districts)):
        print(f"\t{index} -> {districts[index]['district_name']}")


def check_vaccine_availability(data, age, no_of_vaccine):
    centers = data["centers"]
    vaccine_available = False

    for a_center in centers:
        center_name = a_center['name']
        logger.debug(f"Processing center '{center_name}'")

        for a_session in a_center['sessions']:
            min_age = a_session['min_age_limit']
            capacity = a_session['available_capacity']
            date = a_session['date']

            if min_age <= age and capacity >= no_of_vaccine:
                logger.debug(f"'{capacity}' vaccine(s) are available on center '{center_name}' on date '{date}'")
                vaccine_available = True

    return vaccine_available


def _build_email_body():
    msg = f"""Subject: Vaccines are available in your area.

    Hi, 
        Register now, vaccines are available in your area.
    """

    return msg


if __name__ == '__main__':
    age = input("Enter your age: ")
    min_count = input("Minimum number of doses you are looking for: ")
    mobile_no = input("Enter your mobile number: ")

    if not generate_otp(mobile_no):
        exit(1)

    logger.info("OTP sent successfully")

    otp = input("Enter the OTP: ")

    if not confirm_otp(otp):
        exit(1)

    logger.info("OTP confirmed successfully")

    states = get_states()
    if states is None:
        exit(1)

    clear_screen()
    print("Chose your states from following:")
    print_states(states)
    state_index = input("Your state: ")
    user_state = states[int(state_index)]

    if not user_state:
        logger.error("Invalid state selected")

    state_id = user_state["state_id"]

    districts = get_districts(state_id)
    if districts is None:
        exit(1)

    clear_screen()
    print("Chose your district from following:")
    print_districts(districts)
    district_index = input("Your district: ")
    user_district = districts[int(district_index)]

    district_id = user_district["district_id"]

    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s  %(levelname)s  %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)

    clear_screen()

    logger.info("Users will be notified when the vaccines are available.")

    while True:
        centers_json = get_calendar(district_id)

        if centers_json is None:
            exit(1)

        if check_vaccine_availability(centers_json, int(age), int(min_count)):
            for target in notification_targets:
                _send_email(target, _build_email_body())

            logger.info(f"Vaccines are available. User(s) notified")
        else:
            logger.warning(
                f"'{min_count}' vaccine dose(s) are not available in '{user_district['district_name']}' for '{age}' "
                f"years old "
            )

        time.sleep(5 * 60)
