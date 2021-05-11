import smtplib
import ssl
import time
from datetime import datetime, timedelta
import requests
import logging
import urllib3
from math import sin, cos, sqrt, atan2, radians
from playsound import playsound

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

auth = dict()
base_url = "https://cdn-api.co-vin.in/api"

today = datetime.now().strftime('%d-%m-%Y')
yesterday = (datetime.now() - timedelta(1)).strftime('%d-%m-%Y')
tomorrow = (datetime.now() + timedelta(1)).strftime('%d-%m-%Y')

port = 465
smtp_server = ""

# make sure less secure access is ON for sender account^M
# https://myaccount.google.com/lesssecureapps
sender_email = ""  # TODO: set your email address here
password = ""  # TODO: set your password here
notification_targets = []  # TODO: add the users email address who should be notified when the vaccine is available

user_lat = 0
user_long = 0
radius = 0


def clear_screen():
    import os

    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


def audio_alert():
    from os import path
    filename = "voice_alert.mp3"

    if not path.exists(filename):
        from gtts import gTTS
        mytext = 'Alert! vaccines available'
        language = 'en'
        myobj = gTTS(text=mytext, lang=language, slow=False)
        myobj.save(filename)

    print("press ctrl+c to stop the notification")

    while True:
        try:
            playsound(filename)
            time.sleep(0.3)
        except KeyboardInterrupt as e:
            print("audio notification stopped")
            return


def restart_audio_alert():
    from os import path
    filename = "restart_voice_alert.mp3"

    if not path.exists(filename):
        from gtts import gTTS
        mytext = 'Alert! restart the script'
        language = 'en'
        myobj = gTTS(text=mytext, lang=language, slow=False)
        myobj.save(filename)

    print("press ctrl+c to stop the notification")

    while True:
        try:
            playsound(filename)
            time.sleep(0.3)
        except KeyboardInterrupt as e:
            print("audio notification stopped")
            return


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


def geographical_distance(center):
    R = 6373.0

    lat1 = radians(user_lat)
    lon1 = radians(user_long)
    lat2 = radians(center['lat'])
    lon2 = radians(center['long'])

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


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
    try:
        url = base_url + "/v2/auth/public/generateOTP"
        payload = {"mobile": number}

        response = requests.post(url, json=payload, verify=False)

        if not _is_response_successful(response):
            logger.error("Could not generate OTP")
            return False

        data = response.json()
        auth["txnId"] = data["txnId"]
        return True
    except requests.exceptions.ConnectionError as e:
        logger.error("Internet connection is not available")


def confirm_otp(otp):
    try:
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
    except requests.exceptions.ConnectionError as e:
        logger.error("Internet connection is not available")


def centers_in_radius(center):
    center_distance = geographical_distance(center)
    if center_distance <= radius:
        return True

    logger.debug(f"Center '{center['name']} is too far({center_distance}km), not considering it'")
    return False


def get_centers(district_id):
    try:
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
            logger.error("failed to get centers")
            return None

        centers_json = rsp.json()
        centers = centers_json["centers"]

        # location param recevied are invalid from cowin, look at bug https://github.com/cowinapi/developer.cowin/issues/1
        # filtered_centers = filter(centers_in_radius, centers)
        filtered_centers = centers
        sorted_centers = sorted(filtered_centers, key=geographical_distance)

        logger.debug(sorted_centers)
        return sorted_centers
    except requests.exceptions.ConnectionError as e:
        logger.error("Internet connection is not available")


def get_states():
    try:
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
    except requests.exceptions.ConnectionError as e:
        logger.error("Internet connection is not available")


def print_states(states):
    for index in range(len(states)):
        print(f"\t{index} -> {states[index]['state_name']}")


def get_districts(state_id):
    try:
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
    except requests.exceptions.ConnectionError as e:
        logger.error("Internet connection is not available")


def print_districts(districts):
    for index in range(len(districts)):
        print(f"\t{index} -> {districts[index]['district_name']}")


def get_beneficiaries():
    url = base_url + "/v2/appointment/beneficiaries"
    headers = {
        "authorization": f"Bearer {auth['token']}",
        "accept": "application/json",
        "accept-language": "en-US,en;q=0.9",
        "accept-encoding": "gzip, deflate, br",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
        "origin": "https://selfregistration.cowin.gov.in",
        "referer": "https://selfregistration.cowin.gov.in/",
        "sec-ch-ua": 'Not A;Brand";v="99", "Chromium";v="90", "Google Chrome";v="90"',
        "sec-ch-ua-mobile": "?0",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site"
    }

    print(url)
    print(headers)

    rsp = requests.get(url, headers=headers, verify=False)
    print(rsp)

    if not _is_response_successful(rsp):
        logger.error("failed to get beneficiaries")
        return None

    beneficiaries_json = rsp.json()

    return beneficiaries_json['beneficiaries']


def get_available_capacity(center):
    capacity = 0

    for a_session in center['sessions']:
        capacity += a_session['available_capacity']

    return capacity


def check_vaccine_availability(centers, age, no_of_vaccine):
    vaccine_available = False
    vc_centers = []

    for center_index in range(len(centers)):
        center_name = centers[center_index]['name']
        logger.debug(f"Processing center '{center_name}', distance '{geographical_distance(centers[center_index])}'")

        for a_session in centers[center_index]['sessions']:
            min_age = a_session['min_age_limit']
            capacity = a_session['available_capacity']
            date = a_session['date']

            logger.debug(f"Center '{center_name}', Date '{date}', Min age '{min_age}', Capacity '{capacity}'")

            if min_age <= age and capacity >= no_of_vaccine:
                logger.debug(f"'{capacity}' vaccine(s) are available on center '{center_name}' on date '{date}'")
                vaccine_available = True
                vc_centers.append(center_index)
                break

    return vaccine_available, vc_centers


def _build_email_body(centers, vc_center_indexs, email):
    count = 1
    msg = ""
    if email:
        msg += f"""Subject: Vaccines are available in your area.

        Hi, 
    
        """
    msg += "Register now, vaccines are available in your area at the following centers:\n"

    for i in vc_center_indexs:
        center = centers[i]
        msg += f"\t{count} '{center['name']}' distance '{geographical_distance(center)}' Capacity " \
               f"'{get_available_capacity(center)}', Pincode '{center['pincode']}'\n "
        count += 1

        if count >= 10:
            break;

    return msg


if __name__ == '__main__':
    age = int(input("Enter your age: "))
    min_count = int(input("Minimum number of doses you are looking for: "))
    radius = int(input("Radius in Km: "))
    user_lat_s, user_long_s = input("Your location latitude and longitude(28.150031, 75.466037): ").split(",")
    user_lat = float(user_lat_s)
    user_long = float(user_long_s)

    mobile_no = input("Enter your registered mobile number: ")

    if not generate_otp(mobile_no):
        exit(1)

    logger.debug("OTP sent successfully")

    otp = input("Enter the OTP: ")

    if not confirm_otp(otp):
        exit(1)

    logger.debug("OTP confirmed successfully")

    states = get_states()
    if states is None:
        exit(1)

    clear_screen()
    print("Chose your states from following:")
    print_states(states)
    state_index = input("Your state index: ")
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
    district_index = input("Your district index: ")
    user_district = districts[int(district_index)]

    district_id = user_district["district_id"]

    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s  %(levelname)s  %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)

    clear_screen()

    logger.info("Users will be notified when the vaccines are available.")
    error_count = 0

    while True:
        centers = get_centers(district_id)

        if centers is None:
            error_count += 1

            if error_count >= 5:
                restart_audio_alert()
                logger.error("Script is facing issues, try restarting it")
                exit(1)

            time.sleep(15)
            continue

        error_count = 0

        success, vc_centers_indexes = check_vaccine_availability(centers, int(age), int(min_count))

        if success:
            logger.info(f"Vaccines are available at the following centers.")
            logger.info(_build_email_body(centers, vc_centers_indexes, False))
            logger.debug("notifying user(s)")

            for target in notification_targets:
                try:
                    _send_email(target, _build_email_body(centers, vc_centers_indexes, True))
                except Exception as e:
                    logger.error("Failed to send email to the user")
                    logger.exception(e)

            audio_alert()

        else:
            logger.warning(
                f"'{min_count}' vaccine dose(s) are not available in '{user_district['district_name']}' for '{age}' "
                f"years old "
            )

        time.sleep(30)
