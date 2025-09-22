import os
import json
from pdf2image import convert_from_path
from PIL import Image
import re
import google.generativeai as genai
import io
import time


# --- Helper function to convert Persian/Arabic numerals ---
def to_english_digits(text):
    if not isinstance(text, str):
        text = str(text)
    persian_map = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
    arabic_map = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    return text.translate(persian_map).translate(arabic_map)


# --- Post-processing function to correct common spacing errors ---
def correct_common_spacing_errors(text):
    if not text:
        return ""
    verb_stems_for_mi_ne = (
        r"روم|رود|روی|رویم|روید|روند|کنم|کند|کنی|کنیم|کنید|کنند|شوم|شود|شوی|شویم|شوید|شوند|"
        r"دهم|دهد|دهی|دهیم|دهید|دهند|زنم|زند|زنی|زنیم|زنید|زنند|گیرم|گیرد|گیری|گیریم|گیرید|گیرند|"
        r"گویم|گوید|گویی|گوییم|گویید|گویند|دارم|دارد|داری|داریم|دارید|دارند|باشم|باشد|باشی|باشیم|باشید|باشند|"
        r"آیم|آید|آیی|آییم|آیید|آیند|توانم|تواند|توانی|توانیم|توانید|توانند|یابم|یابد|یابی|یابیم|یابید|یابند|"
        r"سازم|سازد|سازی|سازیم|سازید|سازند|پذیرم|پذیرد|پذیری|پذیریم|پذیرید|پذیرند|گردم|گردد|گردی|گردیم|گردید|گردند|"
        r"بینم|بیند|بینی|بینیم|بینید|بینند|دانم|داند|دانی|دانیم|دانید|دانند|نویسم|نویسد|نویسی|نویسیم|نویسید|نویسند|"
        r"خوانم|خواند|خوانی|خوانیم|خوانید|خوانند|خواهم|خواهد|خواهی|خواهیم|خواهید|خواهند|برم|برد|بری|بریم|برید|برند"
    )
    text = re.sub(r'\b(می|نمی)\s+(' + verb_stems_for_mi_ne + r')\b', r'\1‌\2', text)  # ZWNJ
    text = re.sub(r'\b(می|نمی)(' + verb_stems_for_mi_ne + r')\b', r'\1‌\2', text)  # ZWNJ
    text = text.replace('مییابد', 'می‌یابد')
    text = text.replace('میشود', 'می‌شود')
    text = text.replace('آنها', 'آن‌ها')
    text = re.sub(r'(\S)\s+(ها)\b', r'\1‌ها', text)
    text = re.sub(r'(\S)\s+(ای)\b', r'\1‌ای', text)
    return text


# --- 1. Configure Gemini API Key ---
API_KEY = ""  # Your API Key
genai.configure(api_key=API_KEY)


# --- Function to extract questions as JSON ---
def get_json_from_image_gemini(image_pil_object, page_num_for_log="", total_questions_expected_for_prompt=60,
                               answers_are_bolded=False):
    try:
        img_byte_arr = io.BytesIO()
        image_pil_object.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()
        image_part = {"mime_type": "image/jpeg", "data": img_byte_arr}
        model = genai.GenerativeModel('gemini-1.5-flash')

        correct_option_instruction = ""
        if answers_are_bolded:
            correct_option_instruction = """4.  `'correct_option'`: **به دقت بررسی کن که کدام یک از چهار گزینه با فونت برجسته (بولد) نمایش داده شده است. شماره آن گزینه (۱، ۲، ۳ یا ۴) را به عنوان مقدار این فیلد قرار بده. اگر هیچ گزینه‌ای بولد نیست یا نمی‌توانی با اطمینان تشخیص دهی، این فیلد را `null` قرار بده.**"""
        else:
            correct_option_instruction = """4.  `'correct_option'`: این فیلد را `null` قرار بده (پاسخنامه جداگانه پردازش خواهد شد)."""

        prompt_questions_json_farsi = f"""از این تصویر، تمام سوالات چهارگزینه‌ای (فارسی یا انگلیسی) را با دقت بسیار بالا استخراج کن. این صفحه بخشی از یک آزمون با حدوداً {total_questions_expected_for_prompt} سوال است.
        برای هر سوال، یک شیء JSON با مشخصات زیر ایجاد کن:

        1.  `'number'`: شماره سوال (در صورت امکان به صورت عدد صحیح، در غیر این صورت به صورت رشته).
        2.  `'question'`: متن کامل سوال.
            * **بسیار مهم: این فیلد باید فقط و فقط شامل متن اصلی و کامل صورت سوال باشد. متن گزینه‌ها به هیچ عنوان نباید در این فیلد تکرار شود. اگر بعد از استخراج متوجه شدی که به اشتباه متن گزینه‌ها را هم در این فیلد قرار داده‌ای، حتماً آن‌ها را حذف کن و فقط متن خالص صورت سوال را نگه دار.**
            * اگر یک متن ریدینگ (گذر متن) وجود دارد که به یک یا چند سوال مرتبط است، متن کامل این گذر را در ابتدای فیلد `'question'` برای هر یک از سوالات مرتبط قرار بده. سپس متن اصلی سوال را بعد از متن ریدینگ (مثلاً با دو خط جدید فاصله) اضافه کن. فیلد جداگانه‌ای برای 'passage' ایجاد نکن.
            * اگر سوال به یک نمودار، شکل، یا تصویر اشاره دارد، عبارت "(This question has an image, add it manually)" را در ابتدای متن فیلد `'question'` (بعد از متن ریدینگ، در صورت وجود) قرار بده و سپس متن کامل سوال اصلی را بیاور.
            * فرمول‌های ریاضی در متن سوال باید به صورت متن ساده کاملاً خوانا و خطی بازنویسی شوند. به عنوان مثال، برای توان از `^` (مانند `x^2`)، برای رادیکال از `sqrt()` (مانند `sqrt(a+b)`), برای کسر از `/` همراه با پرانتزگذاری مناسب (مانند `(a+b)/(c-d)`) و برای توابع مثلثاتی از نام‌های رایج (مانند `sin(x)`, `arctan(y)` یا `tg^-1(y)`) استفاده شود. مطلقاً و تحت هیچ شرایطی از تگ‌های HTML (مانند `<sup>` یا `<sub>`) یا فرمت LaTeX برای نمایش فرمول‌ها استفاده نکن.
            * توجه بسیار ویژه به علائم نگارشی فارسی: در تمام متون فارسی استخراج شده (صورت سوال، گزینه‌ها، متن ریدینگ)، علائم نگارشی استاندارد فارسی، به خصوص استفاده ۱۰۰٪ صحیح از نیم‌فاصله‌ها را رعایت کن. به عنوان مثال، کلماتی مانند «می‌شود»، «خانه‌ها»، «کتاب‌هایم» باید با نیم‌فاصله نوشته شوند، نه «میشود»، «خانه ها» یا «کتاب هایم». همچنین فاصله‌گذاری درست بعد از نقطه، ویرگول و سایر علائم رعایت شود.
        3.  `'options'`: لیستی شامل چهار رشته که فقط متن خالص گزینه‌های سوال را به ترتیب صحیح (۱، ۲، ۳، ۴) نشان می‌دهند. هرگونه شماره‌گذاری اولیه گزینه (مانند (۱)، الف)، ۱.) باید از ابتدای متن گزینه حذف شود. فرمول‌ها در گزینه‌ها نیز باید مشابه فرمول‌های سوال (یعنی فقط متن ساده و خوانا، بدون HTML یا LaTeX) باشند و علائم نگارشی در گزینه‌ها نیز رعایت شود.
        {correct_option_instruction} # این متغیر در کد پایتون بر اساس انتخاب کاربر مقداردهی می‌شود

        تمام سوالات موجود در این تصویر را استخراج کن. خروجی را *فقط و فقط* به صورت یک لیست JSON واحد و معتبر از اشیاء برگردان. هر شیء باید یک سوال را نمایندگی کند.
        مطمئن شو که JSON از نظر ساختاری کاملاً صحیح و خوش‌فرمت است. هیچ متن اضافی، توضیح، یا قالب‌بندی مارک‌داون قبل یا بعد از لیست JSON ننویس.
        """
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json"
        )
        response = model.generate_content([prompt_questions_json_farsi, image_part],
                                          generation_config=generation_config)

        if response and response.parts:
            raw_text = response.text.strip()
            start_index = raw_text.find('[')
            end_index = raw_text.rfind(']')
            if start_index != -1 and end_index != -1 and end_index > start_index:
                json_text = raw_text[start_index: end_index + 1]
                try:
                    questions_data = json.loads(json_text)
                    if isinstance(questions_data, list):
                        for q_item in questions_data:
                            if isinstance(q_item, dict):
                                if 'question' in q_item and isinstance(q_item['question'], str):
                                    q_item['question'] = correct_common_spacing_errors(q_item['question'])
                                if 'options' in q_item and isinstance(q_item['options'], list):
                                    q_item['options'] = [
                                        correct_common_spacing_errors(opt) if isinstance(opt, str) else opt for opt in
                                        q_item['options']]
                    return questions_data if isinstance(questions_data, list) else None
                except json.JSONDecodeError as json_err:
                    print(f"ERROR: JSONDecodeError for questions on page {page_num_for_log}: {json_err}")
                    print(f"Attempted JSON text (first 300 chars): {json_text[:300]} ...")
                    return None
            else:
                print(
                    f"ERROR: Valid JSON list for questions not found in Gemini's response for page {page_num_for_log}.")
                print(f"Received text for questions (first 300 chars): {raw_text[:300]} ...")
                return None
        else:
            print(f"ERROR: No valid response from Gemini for questions on page {page_num_for_log} (JSON).")
            return None
    except Exception as e:
        print(f"ERROR: Exception during Gemini question JSON extraction for page {page_num_for_log}: {e}")
        return None


# --- Function to extract answer key as JSON ---
def get_answer_key_json_from_gemini(image_pil_object, page_num_for_log="", total_questions_expected_for_prompt=60):
    try:
        img_byte_arr = io.BytesIO()
        image_pil_object.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()
        image_part = {"mime_type": "image/jpeg", "data": img_byte_arr}
        model = genai.GenerativeModel('gemini-1.5-flash')

        prompt_answer_key_json_farsi = f"""این تصویر به احتمال زیاد حاوی صفحه کلید پاسخنامه یک آزمون چهارگزینه‌ای شامل حدوداً {total_questions_expected_for_prompt} سوال است.
وظیفه شما این است که با دقت تمام صفحه را تحلیل کرده و **تمام جفت‌های «شماره سوال» به «گزینه صحیح» موجود در کل صفحه** را استخراج کنید (تا سقف {total_questions_expected_for_prompt} پاسخ).

پاسخنامه ممکن است به فرمت‌های مختلفی ارائه شده باشد، مانند:
- یک جدول با ستون‌هایی برای «شماره سوال» و «گزینه صحیح». **اگر جدول چندین مجموعه از این ستون‌ها را در کنار هم دارد (مثلاً دو یا چند بخش پاسخنامه در یک جدول که هر کدام شامل شماره سوال و گزینه صحیح هستند)، لطفاً تمام جفت‌ها از تمام این بخش‌ها را استخراج کن و در یک شیء JSON واحد ادغام نما.**
- یک لیست ساده (مثلاً: «۱- الف»، «۲- ۳»، «۳- ب»).
- دو یا چند ستون از جفت‌های «شماره سوال - گزینه صحیح» که در کنار هم در صفحه چیده شده‌اند.

لطفاً تمام این جفت‌ها را شناسایی کرده و آن‌ها را *فقط و فقط* به صورت یک **شیء JSON واحد و خوش‌ساخت** برگردانید.
کلیدهای این شیء JSON باید شماره سوالات باشند (به رشته یا عدد صحیح تبدیل شوند).
مقادیر باید شماره گزینه‌های صحیح مربوطه باشند (به عدد صحیح تبدیل شوند، معمولاً ۱، ۲، ۳ یا ۴).

مثال برای فرمت خروجی (که می‌تواند شامل تمام سوالات باشد):
{{"1": 2, "2": 4, "3": 1, ..., "31": 1, "32": 3, ..., "{total_questions_expected_for_prompt}": 4}}

- اطمینان حاصل کنید که شماره سوالات به درستی خوانده می‌شوند.
- اطمینان حاصل کنید که شماره گزینه‌های صحیح به درستی شناسایی می‌شوند (در صورت امکان و لزوم، حروف را به عدد معادل تبدیل کنید، مثلاً الف=۱، ب=۲، ج=۳، د=۴). اگر تبدیل به عدد ممکن نیست، گزینه را به صورت رشته برگردانید.
- اگر اعداد (چه شماره سوال و چه شماره گزینه) به فارسی یا عربی هستند، لطفاً آن‌ها را در خروجی JSON به ارقام استاندارد انگلیسی (0-9) تبدیل کنید.
- هرگونه متن دیگر در صفحه، مانند عنوان‌ها، سرتیترها، پانویس‌ها یا شماره صفحات را نادیده بگیرید.
- اگر هیچ پاسخنامه واضحی در صفحه یافت نشد، یک شیء JSON خالی به این صورت برگردانید: {{}}

در پاسخ خود، *فقط و فقط* شیء JSON را ارائه دهید و از هیچ متن اضافی، توضیح یا قالب‌بندی مارک‌داون استفاده نکنید.
"""
        generation_config = genai.types.GenerationConfig(
            response_mime_type="application/json"
        )
        response = model.generate_content([prompt_answer_key_json_farsi, image_part],
                                          generation_config=generation_config)

        if response and response.parts:
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()
            if not raw_text:
                print(f"WARNING: Gemini's response for answer key on page {page_num_for_log} was empty after strip.")
                return {}
            try:
                answer_data = json.loads(raw_text)
                if isinstance(answer_data, dict):
                    cleaned_answer_key = {}
                    for k, v_raw in answer_data.items():
                        try:
                            q_num = int(to_english_digits(str(k)))
                            v_str_cleaned = to_english_digits(str(v_raw)).strip()
                            correct_opt = -1
                            if v_str_cleaned.isdigit() and 1 <= int(v_str_cleaned) <= 4:
                                correct_opt = int(v_str_cleaned)
                            elif isinstance(v_raw, str):
                                v_char = v_raw.strip()
                                if v_char == "الف" or v_char.lower() == "a" or v_char == "۱":
                                    correct_opt = 1
                                elif v_char == "ب" or v_char.lower() == "b" or v_char == "۲":
                                    correct_opt = 2
                                elif v_char == "ج" or v_char.lower() == "c" or v_char == "۳":
                                    correct_opt = 3
                                elif v_char == "د" or v_char.lower() == "d" or v_char == "۴":
                                    correct_opt = 4
                            if correct_opt != -1:
                                cleaned_answer_key[q_num] = correct_opt
                            else:
                                print(
                                    f"WARNING: Invalid correct option '{v_raw}' for question {q_num} in answer key JSON (page {page_num_for_log}).")
                        except ValueError:
                            print(
                                f"WARNING: Invalid number format in answer key JSON: key='{k}', value='{v_raw}' (page {page_num_for_log}).")
                    return cleaned_answer_key
                else:
                    print(
                        f"ERROR: Gemini's response for answer key on page {page_num_for_log} was not a JSON object: {type(answer_data)}")
                    print(f"Received text for answer key (first 300 chars): {raw_text[:300]}...")
                    return {}
            except json.JSONDecodeError as json_err:
                print(f"ERROR: JSONDecodeError for answer key on page {page_num_for_log}: {json_err}")
                print(f"Attempted JSON text for answer key (first 300 chars): {raw_text[:300]} ...")
                return {}
        else:
            print(f"ERROR: No valid response from Gemini for answer key on page {page_num_for_log}.")
            return {}
    except Exception as e:
        print(f"ERROR: Exception during Gemini answer key JSON extraction for page {page_num_for_log}: {e}")
        return {}


# --- Main script settings ---
pdf_filename = input("Enter PDF filename (e.g., soalat.pdf): ")

total_questions_input = input("Enter the total number of questions in the PDF (e.g., 60): ")
try:
    TOTAL_QUESTIONS_EXPECTED = int(total_questions_input)
    if TOTAL_QUESTIONS_EXPECTED <= 0:
        print("ERROR: Invalid total number of questions. Please enter a positive number.")
        exit()
except ValueError:
    print("ERROR: Invalid input for total number of questions. Exiting.")
    exit()

answer_key_input_type = input(
    "Enter answer key page number (e.g., 8) OR type 'bold' if answers are bolded in questions (or 0 if no answer key): ").strip().lower()
ANSWER_KEY_PAGE_NUMBER = 0
ANSWERS_ARE_BOLDED = False

if answer_key_input_type == 'bold':
    ANSWERS_ARE_BOLDED = True
    print("INFO: Script will try to detect bolded correct answers within question pages.")
elif answer_key_input_type.isdigit():
    ANSWER_KEY_PAGE_NUMBER = int(answer_key_input_type)
    if ANSWER_KEY_PAGE_NUMBER == 0:
        print("INFO: No separate answer key page will be processed.")
    else:
        print(f"INFO: Answer key will be processed from page {ANSWER_KEY_PAGE_NUMBER}.")
else:
    print(
        "WARNING: Invalid input for answer key page/type. Assuming no separate answer key page and answers are not bolded.")

output_folder = 'pages_output'
os.makedirs(output_folder, exist_ok=True)

print(f"Converting PDF '{pdf_filename}' to images...")
try:
    pages = convert_from_path(pdf_filename, dpi=300, poppler_path=None)
    print(f"{len(pages)} pages extracted from PDF.")
except Exception as e:
    print(f"ERROR: Failed to convert PDF to images: {e}")
    print("Ensure poppler is installed and in PATH, or specify poppler_path in convert_from_path.")
    exit()

all_questions = []
answer_key = {}  # This will be populated if a separate answer key page is processed

# --- Process each page ---
for i, page_pil_object in enumerate(pages):
    current_page_num = i + 1
    page_num_str_for_log = str(current_page_num)
    print(f"\n--- Processing page {current_page_num} ---")

    if not ANSWERS_ARE_BOLDED and ANSWER_KEY_PAGE_NUMBER != 0 and current_page_num == ANSWER_KEY_PAGE_NUMBER:
        print(f"Page {current_page_num} identified as separate answer key page. Extracting answer key as JSON...")
        extracted_answers = get_answer_key_json_from_gemini(page_pil_object, page_num_str_for_log,
                                                            TOTAL_QUESTIONS_EXPECTED)
        if extracted_answers:
            answer_key.update(extracted_answers)
            print(f"{len(extracted_answers)} answers extracted from answer key page and added.")
            if not extracted_answers:
                print(f"WARNING: Extracted answer key JSON for page {current_page_num} was empty.")
        else:
            print(f"ERROR: No valid answer key JSON extracted from page {current_page_num}.")
    else:
        # Process as a question page (which might include detecting bolded answers if ANSWERS_ARE_BOLDED is True)
        print(f"Processing page {current_page_num} for questions...")
        page_questions_list = get_json_from_image_gemini(page_pil_object, page_num_str_for_log,
                                                         TOTAL_QUESTIONS_EXPECTED, ANSWERS_ARE_BOLDED)
        if page_questions_list:
            processed_count = 0
            for q_data in page_questions_list:
                if isinstance(q_data, dict) and \
                        'number' in q_data and \
                        'question' in q_data and \
                        'options' in q_data and \
                        isinstance(q_data['options'], list) and \
                        len(q_data['options']) == 4:
                    try:
                        q_data['number'] = int(to_english_digits(q_data['number']))
                        # If answers are bolded, correct_option should already be in q_data from Gemini
                        if not ANSWERS_ARE_BOLDED:
                            q_data['correct_option'] = None  # Initialize if not expecting bold detection
                        elif 'correct_option' not in q_data:  # If bold detection was expected but failed
                            q_data['correct_option'] = None
                            print(
                                f"WARNING: Expected bolded answer for Q{q_data['number']} on page {current_page_num} but not found by Gemini.")

                        all_questions.append(q_data)
                        processed_count += 1
                    except ValueError:
                        print(
                            f"WARNING: Invalid question number '{q_data.get('number')}' in JSON for page {current_page_num}.")
                else:
                    print(
                        f"WARNING: Invalid question JSON structure from page {current_page_num}: {str(q_data)[:100]}...")
            print(f"{processed_count} valid questions found and added from page {current_page_num}.")
        else:
            print(f"ERROR: No questions (JSON) extracted or invalid format from page {current_page_num}.")

    print(f"Waiting for {1} second(s)...")
    time.sleep(1)  # WARNING: High risk of quota error!

# --- Add correct options to questions (only if not detected as bolded) ---
if not ANSWERS_ARE_BOLDED and answer_key:
    print("\nAdding correct options to extracted questions from separate answer key...")
    questions_with_answers_count = 0
    for q in all_questions:
        q_number = q.get("number")
        if q_number is not None and q_number in answer_key:
            q["correct_option"] = answer_key[q_number]
            questions_with_answers_count += 1
    print(f"Correct option added for {questions_with_answers_count} questions using separate answer key.")
elif not ANSWERS_ARE_BOLDED and not answer_key and len(all_questions) > 0 and ANSWER_KEY_PAGE_NUMBER != 0:
    print(
        "WARNING: Separate answer key was specified but is empty or was not processed. Correct options were not added.")
elif ANSWERS_ARE_BOLDED:
    print("\nCorrect options were expected to be detected as bolded by Gemini within each question's JSON.")
    # Optionally, count how many were successfully detected
    bold_detected_count = sum(1 for q in all_questions if q.get('correct_option') is not None)
    print(f"{bold_detected_count} questions have a 'correct_option' (presumably from bold detection).")

# --- Save to JSON file ---
if all_questions:
    seen_numbers = set()
    unique_questions = []
    all_questions.sort(key=lambda x: x.get('number', float('inf')))
    for q in all_questions:
        q_num = q.get('number')
        if q_num is not None and q_num not in seen_numbers:
            unique_questions.append(q)
            seen_numbers.add(q_num)
        elif q_num is None:
            print(f"WARNING: Question found without a number: {q.get('question', '')[:50]}...")

    output_json_filename = os.path.splitext(pdf_filename)[0] + "_extracted_questions.json"
    with open(output_json_filename, "w", encoding="utf-8") as f:
        json.dump(unique_questions, f, ensure_ascii=False, indent=2)
    print(f"\n{len(unique_questions)} unique questions extracted and saved to '{output_json_filename}'.")
else:
    print("\nNo questions were extracted.")
