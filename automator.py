import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# --- تنظیمات ---
LOGIN_URL = "https://biazmoon.com/"
# ⚠️ اطلاعات کاربری واقعی خود را در اینجا و به صورت دستی وارد کنید
YOUR_USERNAME = "your email"
YOUR_PASSWORD = "your password"

JSON_FILE = "example.json"
QQQ_SESSION_NUMBER = "1403"
TAGS_TO_ADD = ["آزمون کارشناسی ارشد ادیان و عرفان و تاریخ فرهنگ و تمدن اسلامی"]
CREATE_QUESTION_URL = "https://biazmoon.com/User/Lessons/CreateQuestion/211"


def login(driver, wait):
    """
    تابعی برای انجام خودکار فرآیند لاگین
    """
    try:
        print("Attempting to log in...")
        driver.get(LOGIN_URL)
        username_field = wait.until(EC.presence_of_element_located((By.ID, 'UserName')))
        password_field = driver.find_element(By.ID, 'Password')
        username_field.send_keys(YOUR_USERNAME)
        password_field.send_keys(YOUR_PASSWORD)
        login_button = driver.find_element(By.CSS_SELECTOR, '.LF_Submit_Btn')
        login_button.click()
        print("Waiting for user panel to load...")
        wait.until(EC.presence_of_element_located((By.LINK_TEXT, 'درس ها')))
        print("✅ Login successful and user panel loaded.")
        return True
    except Exception as e:
        print(f"!!! ERROR during login: {e}")
        driver.save_screenshot("error_login.png")
        print("Login failed. Screenshot saved to 'error_login.png'.")
        return False


def automate_question_entry():
    """
    تابع اصلی برای ورود خودکار سوالات پس از لاگین
    """
    driver = webdriver.Chrome()
    driver.maximize_window()
    wait = WebDriverWait(driver, 20)
    try:
        # مرحله ۱: لاگین خودکار
        if not login(driver, wait):
            return

        # مرحله ۲: رفتن به صفحه ایجاد سوال
        print(f"Navigating to create question page: {CREATE_QUESTION_URL}")
        driver.get(CREATE_QUESTION_URL)
        # time.sleep(2)

        # مرحله ۳: خواندن سوالات از فایل
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            questions = json.load(f)
        print(f"{len(questions)} questions loaded from {JSON_FILE}.")
        questions.sort(key=lambda q: q.get('number', 0))

        # مرحله ۴: شروع حلقه ورود سوالات
        for q_index, q_data in enumerate(questions):
            question_number = q_data.get('number')
            question_text_from_json = q_data.get('question', "")
            options = q_data.get('options')
            correct_option_value = q_data.get('correct_option')

            # اعتبارسنجی اولیه داده‌های سوال
            if not all([question_number, question_text_from_json, options, correct_option_value]) or len(options) != 4:
                print(f"**WARNING: Data for question number {question_number} is incomplete. Skipping.**")
                continue

            print(f"\n--- Starting to enter question number {question_number} ({q_index + 1}/{len(questions)}) ---")
            try:
                question_textarea = wait.until(EC.presence_of_element_located((By.ID, "QuestionText")))
                question_textarea.clear()
                question_textarea.send_keys(question_text_from_json)
                print("Question text entered.")

                # --- این بخش کامل از کد اول شما بازیابی و یکپارچه شد ---
                correct_option_index = None
                try:
                    correct_option_index = int(correct_option_value)
                except ValueError:
                    print(f"**WARNING: correct_option برای سوال {question_number} عدد نیست. رد می‌شویم.**")
                    continue

                option_text_fields = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".Option .QuestionAnswer")))
                correct_option_checkboxes = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".Option .ChoiceInput")))

                # ابتدا تمام چک‌باکس‌های قبلی را غیرفعال می‌کنیم
                for cb in correct_option_checkboxes:
                    if cb.is_selected():
                        driver.execute_script("arguments[0].click();", cb)
                # time.sleep(0.2)

                # متن هر چهار گزینه را وارد می‌کنیم
                for i in range(4):
                    option_text_fields[i].clear()
                    option_text_fields[i].send_keys(options[i])
                print("Options entered.")

                # گزینه صحیح را تیک می‌زنیم
                if 1 <= correct_option_index <= 4:
                    correct_checkbox_to_select = correct_option_checkboxes[correct_option_index - 1]
                    driver.execute_script("arguments[0].checked = true;", correct_checkbox_to_select)
                    print(f"Option {correct_option_index} selected as correct answer.")
                else:
                    print(f"WARNING: Invalid correct_option index '{correct_option_index}'")
                # --- پایان بخش بازیابی شده ---

                # بخش وارد کردن تگ‌ها
                if TAGS_TO_ADD:
                    print(f"Attempting to add {len(TAGS_TO_ADD)} tags...")
                    for tag_to_add in TAGS_TO_ADD:
                        try:
                            tag_input_field = wait.until(EC.presence_of_element_located((By.ID, "search-tag-input")))
                            tag_input_field.clear()
                            tag_input_field.send_keys(tag_to_add)

                            search_tag_button = wait.until(EC.element_to_be_clickable((By.ID, "search-tag-button")))
                            search_tag_button.click()
                            # time.sleep(1.5)

                            unique_tag_result_xpath = f"//div[@id='search-tag-list-container']/div/button[contains(@class, 'tag-selector-item')]"
                            tag_element_to_click = wait.until(
                                EC.element_to_be_clickable((By.XPATH, unique_tag_result_xpath)))

                            driver.execute_script("arguments[0].click();", tag_element_to_click)
                            print(f"  - Tag '{tag_to_add}' added successfully.")
                            # time.sleep(0.5)
                        except Exception as tag_e:
                            print(f"  - !!! WARNING: Failed to add tag '{tag_to_add}'. Reason: {tag_e}")
                            continue

                # بخش شماره جلسه و تایید نهایی
                session_number_field = wait.until(EC.presence_of_element_located((By.ID, "SessionNumber")))
                session_number_field.clear()
                session_number_field.send_keys(QQQ_SESSION_NUMBER)
                print(f"Session number '{QQQ_SESSION_NUMBER}' entered.")

                confirm_button = wait.until(EC.element_to_be_clickable((By.ID, "ConfirmQuestionBtn")))
                confirm_button.click()

                # time.sleep(2)
                print(f"✅ Question {question_number} confirmed and added.")

            except Exception as e:
                print(f"!!! ERROR processing question number {question_number}: {e}")
                driver.save_screenshot(f"error_q_{question_number}.png")
                print(f"Screenshot saved. Continuing with the next question...")
                driver.get(CREATE_QUESTION_URL)
                continue

        print("\n✅ Question entry process completed.")
    except Exception as main_e:
        print(f"\n!!! GENERAL ERROR in the program: {main_e}")
    finally:
        print("\n✅ Program finished. The browser will remain open for you to inspect.")

        question_textarea = wait.until(EC.presence_of_element_located((By.ID, "QuestionText")))
        question_textarea.clear()
        question_textarea.send_keys("***************شما یک دقیقه وقت دارید تا سوالات را برسی کرده و گزینه ذخیره سوالات تایید شده را بزنید، در غیر این صورت بدون ذخیره شدن مرورگر بسته خواهد شد.**********************")
        time.sleep(100000)
        driver.quit()


if __name__ == "__main__":
    automate_question_entry()
