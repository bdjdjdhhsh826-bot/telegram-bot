import asyncio
import re
import os
from telethon import TelegramClient, events

# بيانات حسابك
API_ID = 23503199
API_HASH = "dcdf6bdd8cfea0ad558b10ec2c1eb9dc"

SESSION_NAME = "session_user"
BOT_USERNAME = "@wsotp200bot"
FIRE_SMS_BOT = "@Fire_sms_bot"

# ================= جروب المتابعة =================
TARGET_GROUP = "https://t.me/FTH_OTP_Group"

# متغيرات عامة
bot_messages = {}
current_number = None
current_message_id = None
sending_active = True


# ================= دوال استخراج الكود من الأزرار =================

def extract_code_from_button_text(button_text):
    """استخراج الكود من النص الموجود داخل الزر"""
    if not button_text:
        return None
    
    button_text = button_text.strip()
    
    # تنسيق 1: كود مع رمز المفتاح 🔑 273-028
    match = re.search(r'🔑\s*(\d{3})-(\d{3})', button_text)
    if match:
        code = match.group(1) + match.group(2)
        print(f"      ✅ كود مع مفتاح: {code}")
        return code
    
    # تنسيق 2: كود مع رمز المفتاح和各种 رموز
    match = re.search(r'🔑\s*(\d{6})', button_text)
    if match:
        code = match.group(1)
        print(f"      ✅ كود 6 أرقام مع مفتاح: {code}")
        return code
    
    # تنسيق 3: كود من 6 أرقام متصلة
    if button_text.isdigit() and len(button_text) == 6:
        print(f"      ✅ كود 6 أرقام: {button_text}")
        return button_text
    
    # تنسيق 4: كود على شكل XXX-XXX
    match = re.match(r'^(\d{3})-(\d{3})$', button_text)
    if match:
        code = match.group(1) + match.group(2)
        print(f"      ✅ كود بصيغة XXX-XXX: {code}")
        return code
    
    # تنسيق 5: البحث عن 6 أرقام في أي مكان
    match = re.search(r'(\d{6})', button_text)
    if match:
        code = match.group(1)
        print(f"      ✅ 6 أرقام من النص: {code}")
        return code
    
    # تنسيق 6: البحث عن أرقام بصيغة XXX-XXX
    match = re.search(r'(\d{3})-(\d{3})', button_text)
    if match:
        code = match.group(1) + match.group(2)
        print(f"      ✅ أرقام بصيغة XXX-XXX: {code}")
        return code
    
    return None


def extract_code_from_buttons(buttons):
    """استخراج الكود من جميع أزرار الرسالة"""
    if not buttons:
        return None
    
    codes_found = []
    
    for row in buttons:
        for button in row:
            button_text = button.text.strip()
            code = extract_code_from_button_text(button_text)
            if code:
                codes_found.append(code)
    
    if not codes_found:
        return None
    
    codes_found = list(dict.fromkeys(codes_found))
    
    # إعطاء الأولوية للأكواد المكونة من 6 أرقام
    for code in codes_found:
        if len(code) == 6:
            return code
    
    return codes_found[0]


async def get_code_from_message_with_retry(client, chat_id, message_id, timeout=4):
    """محاولة استخراج الكود من رسالة مع انتظار ظهور أزرار جديدة"""
    start_time = asyncio.get_event_loop().time()
    
    while (asyncio.get_event_loop().time() - start_time) < timeout:
        try:
            await asyncio.sleep(0.5)
            msg = await client.get_messages(chat_id, ids=message_id)
            
            if msg and msg.buttons:
                code = extract_code_from_buttons(msg.buttons)
                if code:
                    return code
        except Exception as e:
            pass
    
    return None


def extract_last_4_from_phone_number(text):
    """
    استخراج آخر 4 أرقام من رقم الهاتف في الرسالة
    يدعم الأرقام العادية والمقنعة (مثل 5841****2786)
    """
    if not text:
        return None
    
    print(f"   🔍 البحث عن رقم هاتف في النص: {text[:100]}...")
    
    # 1. البحث عن رقم مقنع بصيغة XXXX****XXXX (أرقام مع نجوم)
    # مثال: 5841****2786
    masked_match = re.search(r'(\d{4})\*{4}(\d{4})', text)
    if masked_match:
        first_part = masked_match.group(1)  # 5841
        last_part = masked_match.group(2)   # 2786
        # نأخذ آخر 4 أرقام من الرقم الكامل
        last_4 = last_part  # آخر 4 أرقام هي 2786
        print(f"   📱 رقم مقنع: {first_part}****{last_part} -> آخر 4 أرقام: {last_4}")
        return last_4
    
    # 2. البحث عن رقم مقنع بصيغة XXXX**XXXX (نجوم أقل)
    masked_match2 = re.search(r'(\d{4})\*{2}(\d{4})', text)
    if masked_match2:
        last_part = masked_match2.group(2)
        print(f"   📱 رقم مقنع بـ **: -> آخر 4 أرقام: {last_part}")
        return last_part
    
    # 3. البحث عن رقم مقنع بصيغة XXXX***XXXX
    masked_match3 = re.search(r'(\d{4})\*{3}(\d{4})', text)
    if masked_match3:
        last_part = masked_match3.group(2)
        print(f"   📱 رقم مقنع بـ ***: -> آخر 4 أرقام: {last_part}")
        return last_part
    
    # 4. البحث عن رقم هاتف كامل بصيغة +XXXXXXXXXXX
    phone_match = re.search(r'\+?(\d{10,15})', text)
    if phone_match:
        full_phone = phone_match.group(1)
        last_4 = full_phone[-4:]
        print(f"   📱 رقم هاتف كامل: {full_phone} -> آخر 4 أرقام: {last_4}")
        return last_4
    
    # 5. البحث عن رقم في سطر Number:
    number_line_match = re.search(r'Number:\s*\+?(\d+)', text, re.IGNORECASE)
    if number_line_match:
        phone = number_line_match.group(1)
        last_4 = phone[-4:] if len(phone) >= 4 else phone
        print(f"   📱 رقم من سطر Number: {phone} -> آخر 4 أرقام: {last_4}")
        return last_4
    
    # 6. البحث عن أرقام بطول 10-15 رقم (أرقام هواتف)
    all_numbers = re.findall(r'\d+', text)
    for num in all_numbers:
        if 10 <= len(num) <= 15:
            last_4 = num[-4:]
            print(f"   📱 رقم هاتف محتمل: {num} -> آخر 4 أرقام: {last_4}")
            return last_4
    
    # 7. البحث عن آخر 4 أرقام في النص (كحل أخير)
    # نبحث عن 4 أرقام بعد كلمة VE أو #VE أو 📞
    last_resort = re.search(r'(?:VE|#VE|📞).*?(\d{4})(?:\D|$)', text)
    if last_resort:
        last_4 = last_resort.group(1)
        print(f"   📱 آخر 4 أرقام (حل أخير): {last_4}")
        return last_4
    
    return None


def extract_last_4_from_number(number):
    """استخراج آخر 4 أرقام من رقم الهاتف مباشرة"""
    if not number:
        return None
    digits = re.sub(r'\D', '', str(number))
    if len(digits) >= 4:
        return digits[-4:]
    return digits


async def get_current_number_from_bot(client):
    """جلب الرقم الحالي من أحدث رسالة في البوت"""
    global current_number, current_message_id
    
    try:
        async for msg in client.iter_messages(FIRE_SMS_BOT, limit=3):
            if msg.text and "📞 𝗡𝘂𝗺𝗯𝗲𝗿:" in msg.text:
                number_match = re.search(r'📞\s*𝗡𝘂𝗺𝗯𝗲𝗿:\s*(\+?\d+)', msg.text)
                if number_match:
                    current_number = number_match.group(1)
                    current_message_id = msg.id
                    last_4 = extract_last_4_from_number(current_number)
                    print(f"📱 الرقم الحالي: {current_number} (آخر 4: {last_4})")
                    return True
        return False
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return False


async def click_change_number_button(client):
    """الضغط على زر تغيير الرقم"""
    global current_number, current_message_id
    
    if not current_message_id:
        print("⚠️ لا يوجد معرف رسالة، جلب أحدث رسالة...")
        await get_current_number_from_bot(client)
        if not current_message_id:
            return False
    
    try:
        msg = await client.get_messages(FIRE_SMS_BOT, ids=current_message_id)
        
        if not msg:
            print("⚠️ الرسالة غير موجودة")
            return False
        
        if not msg.buttons:
            print("⚠️ لا توجد أزرار")
            return False
        
        button_found = False
        for row in msg.buttons:
            for btn in row:
                btn_text = btn.text
                if 'تغيير' in btn_text or '🔄' in btn_text or 'change' in btn_text.lower():
                    print(f"🖱️ الضغط على زر: '{btn_text}'")
                    await btn.click()
                    await asyncio.sleep(1)
                    button_found = True
                    break
            if button_found:
                break
        
        if not button_found:
            print("⚠️ لم يتم العثور على زر تغيير")
            return False
        
        await asyncio.sleep(1)
        
        async for new_msg in client.iter_messages(FIRE_SMS_BOT, limit=5):
            if new_msg.text and "📞 𝗡𝘂𝗺𝗯𝗲𝗿:" in new_msg.text:
                number_match = re.search(r'📞\s*𝗡𝘂𝗺𝗯𝗲𝗿:\s*(\+?\d+)', new_msg.text)
                if number_match:
                    new_number = number_match.group(1)
                    
                    if new_number != current_number:
                        current_number = new_number
                        current_message_id = new_msg.id
                        last_4 = extract_last_4_from_number(current_number)
                        print(f"🔄 رقم جديد: {current_number} (آخر 4: {last_4})")
                        return True
                    else:
                        print(f"⚠️ نفس الرقم، انتظار...")
                        await asyncio.sleep(1)
                        continue
        
        print("⚠️ لم يتم العثور على رقم جديد")
        return False
        
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return False


async def send_number_to_target_bot(client, number):
    """إرسال رقم إلى البوت المستهدف"""
    try:
        last_4 = extract_last_4_from_number(number)
        await client.send_message(BOT_USERNAME, number)
        print(f"📤 إرسال {number} (آخر 4: {last_4})")
        return True
    except Exception as e:
        print(f"❌ فشل إرسال {number}: {e}")
        return False


async def continuous_sending_loop(client):
    """حلقة مستمرة لإرسال الأرقام من بوت Fire SMS"""
    global current_number, current_message_id, sending_active
    
    print("\n🔄 بدء الإرسال المستمر من البوت...")
    
    while sending_active:
        try:
            if not current_number:
                print("⚠️ لا يوجد رقم، جلب من أول رسالة...")
                await get_current_number_from_bot(client)
            
            if current_number:
                await send_number_to_target_bot(client, current_number)
                await asyncio.sleep(1)
                print("🔄 تغيير الرقم...")
                await click_change_number_button(client)
                await asyncio.sleep(1)
            else:
                await asyncio.sleep(2)
                
        except Exception as e:
            print(f"❌ خطأ في حلقة الإرسال: {e}")
            await asyncio.sleep(2)


async def file_numbers_sending_loop(client, file_path):
    """قراءة الأرقام من ملف وإرسالها بالتتابع"""
    global sending_active
    
    if not os.path.exists(file_path):
        print(f"❌ الملف غير موجود: {file_path}")
        return

    print(f"\n📂 بدء قراءة الأرقام من الملف: {file_path}")
    
    try:
        with open(file_path, 'r') as f:
            numbers = [line.strip() for line in f if line.strip()]
        
        print(f"✅ تم العثور على {len(numbers)} رقم")
        
        for number in numbers:
            if not sending_active:
                break
            
            # تنظيف الرقم من أي رموز غير رقمية (اختياري، حسب رغبتك)
            clean_number = re.sub(r'\D', '', number)
            if not clean_number.startswith('+'):
                # إذا كان الرقم لا يبدأ بـ +، قد تحتاج لإضافته أو تركه كما هو حسب البوت
                pass

            await send_number_to_target_bot(client, number)
            
            # انتظار بسيط بين كل رقم والآخر لتجنب الحظر أو التداخل
            await asyncio.sleep(2) 
            
        print("\n✅ انتهى إرسال جميع الأرقام من الملف.")
    except Exception as e:
        print(f"❌ خطأ أثناء قراءة الملف: {e}")


async def main():
    global bot_messages, sending_active
    
    print("\033c", end="")
    
    print("=" * 60)
    print("🤖 أداة التليجرام - استخراج الكود من الأزرار")
    print("=" * 60)
    print()
    
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    
    print("✅ تم تسجيل الدخول\n")
    
    # اختيار الوضع
    print("اختر طريقة العمل:")
    print("1_File number (إرسال أرقام من ملف نصي)")
    print("2_Auto Bot (الإرسال التلقائي من بوت Fire SMS)")
    
    choice = input("\nأدخل رقم الاختيار: ").strip()
    
    print("\n📡 جاري التحقق من الجروب...")
    
    group_chat_id = None
    try:
        entity = await client.get_entity(TARGET_GROUP)
        group_chat_id = entity.id
        print(f"   ✅ {TARGET_GROUP} -> {entity.title}")
    except Exception as e:
        print(f"   ❌ فشل الاتصال بالجروب: {e}")
        return
    
    # ========== معالج البوت المستهدف ==========
    @client.on(events.NewMessage(chats=BOT_USERNAME))
    async def target_bot_handler(event):
        msg_text = event.raw_text
        
        if "In Progress" in msg_text:
            numbers = re.findall(r'\d+', msg_text)
            if numbers:
                phone = numbers[0]
                last_4 = extract_last_4_from_number(phone)
                
                bot_messages[last_4] = {
                    'phone': phone,
                    'message': event.message,
                    'last_4': last_4
                }
                
                print(f"📌 في انتظار الكود: {phone} (آخر 4: {last_4})")
    
    # ========== معالج الجروب المحسن ==========
    @client.on(events.NewMessage(chats=group_chat_id))
    async def group_handler(event):
        msg = event.message
        msg_text = msg.raw_text or ""
        
        # استخراج آخر 4 أرقام من رقم الهاتف
        last_4 = extract_last_4_from_phone_number(msg_text)
        
        # استخراج الكود
        code = None
        if msg.buttons:
            code = extract_code_from_buttons(msg.buttons)
        
        if not code:
            code = await get_code_from_message_with_retry(client, group_chat_id, msg.id, timeout=4)
        
        if last_4 and code:
            if last_4 in bot_messages:
                matched = bot_messages[last_4]
                await matched['message'].reply(code)
                print(f"✅ تم إرسال الكود {code} للرقم الذي ينتهي بـ {last_4}")
                del bot_messages[last_4]
    
    # ========== بدء التشغيل بناءً على الاختيار ==========
    if choice == '1':
        file_path = input("أدخل مسار ملف الأرقام (مثال: numbers.txt): ").strip()
        asyncio.create_task(file_numbers_sending_loop(client, file_path))
    else:
        asyncio.create_task(continuous_sending_loop(client))
    
    print("\n" + "=" * 60)
    print("✅ النظام يعمل الآن...")
    print("=" * 60)
    
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 تم إيقاف البرنامج")
