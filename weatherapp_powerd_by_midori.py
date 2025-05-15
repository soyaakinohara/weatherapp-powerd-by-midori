# --- 修正版天気予報アプリ (Midori Weather App) ---
import customtkinter as ctk
import requests
import json
from PIL import Image
from config import OPENWEATHER_API_KEY  # OpenWeatherMap APIキー
from geminiapi import GEMINI_API_KEY  # Gemini APIキー
from system_prompt import SYSTEM_PROMPT  # システムプロンプト
from datetime import datetime, date
import io
import google.generativeai as genai

# --- Gemini APIの初期化 ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# --- アプリケーションの初期設定 ---
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# --- メインウィンドウの作成 ---
app = ctk.CTk()
app.geometry("800x700")  # ウィンドウサイズを大きく
app.title("天気予報 powered by 緑ちゃんAI")

# --- グローバル変数 ---
NUM_HOURLY_FORECASTS = 3
main_weather_icon = None
hourly_weather_icons = []

# --- Gemini APIで緑ちゃんのコメントを生成 ---
def get_midori_comment(weather_description, temperature):
    try:
        prompt = SYSTEM_PROMPT.format(
            weather_description=weather_description,
            temperature=temperature
        )
        response = model.generate_content(prompt)
        comment = response.text.strip()
        # 70文字以内に制限
        if len(comment) > 70:
            comment = comment[:67] + "..."
        return comment
    except Exception as e:
        print(f"Gemini APIエラー: {e}")
        return "緑ちゃん: 今日も元気に楽しもうね！"

# --- APIリクエスト関数 ---
def get_lat_lon_from_postal_code(postal_code, country_code="JP"):
    base_url = "http://api.openweathermap.org/geo/1.0/zip?"
    postal_code = postal_code.replace("-", "")
    complete_url = base_url + f"zip={postal_code},{country_code}&appid={OPENWEATHER_API_KEY}"
    try:
        response = requests.get(complete_url)
        response.raise_for_status()
        data = response.json()
        return data.get("lat"), data.get("lon"), data.get("name", "不明な都市")
    except Exception as e:
        print(f"郵便番号APIエラー: {e}")
        return None, None, None

def get_current_weather_data(lat=None, lon=None, city_name=None):
    base_url = "http://api.openweathermap.org/data/2.5/weather?"
    if lat is not None and lon is not None:
        complete_url = base_url + f"lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ja"
    else:
        complete_url = base_url + f"appid={OPENWEATHER_API_KEY}&q={city_name}&units=metric&lang=ja"
    try:
        response = requests.get(complete_url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"APIリクエストエラー (current): {e}")
        return None

def get_forecast_data(lat=None, lon=None, city_name=None):
    base_url = "http://api.openweathermap.org/data/2.5/forecast?"
    if lat is not None and lon is not None:
        complete_url = base_url + f"lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ja"
    else:
        complete_url = base_url + f"appid={OPENWEATHER_API_KEY}&q={city_name}&units=metric&lang=ja"
    try:
        response = requests.get(complete_url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"APIリクエストエラー (forecast): {e}")
        return None

def get_today_min_max_temps(forecast_list):
    if not forecast_list:
        return None, None
    
    today = date.today()
    today_temps = []
    
    for item in forecast_list:
        dt_txt = item.get("dt_txt", "")
        if not dt_txt:
            continue
        
        try:
            forecast_date = datetime.strptime(dt_txt.split(" ")[0], "%Y-%m-%d").date()
            if forecast_date == today:
                temp = item.get("main", {}).get("temp")
                if temp is not None:
                    today_temps.append(temp)
        except ValueError:
            continue
    
    if not today_temps:
        return None, None
    
    return min(today_temps), max(today_temps)

# --- 画像処理関数 ---
def load_weather_icon(icon_id, size=(100, 100)):
    if not icon_id:
        return None
    
    try:
        icon_url = f"http://openweathermap.org/img/wn/{icon_id}@2x.png"
        icon_response = requests.get(icon_url, stream=True)
        icon_response.raise_for_status()
        
        img_data = icon_response.content
        img = Image.open(io.BytesIO(img_data))
        
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        return ctk_img
    except Exception as e:
        print(f"アイコン読み込みエラー: {e}")
        return None

# --- 緑ちゃんの画像を読み込む関数 ---
def load_midori_icon(size=(100, 100)):
    try:
        img = Image.open("icon.png")
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        return ctk_img
    except Exception as e:
        print(f"緑ちゃん画像読み込みエラー: {e}")
        return None

# --- UIウィジェットの初期配置 ---
top_frame = ctk.CTkFrame(master=app)
top_frame.pack(pady=10, padx=10, fill="x")

location_label = ctk.CTkLabel(master=top_frame, text="取得中...", font=("Arial", 24, "bold"))
location_label.pack(side="left", padx=10)

postal_code_entry = ctk.CTkEntry(master=top_frame, placeholder_text="郵便番号 (例: 123-4567)", width=150)
postal_code_entry.pack(side="right", padx=5)

refresh_button = ctk.CTkButton(master=top_frame, text="🔄 更新", command=lambda: on_refresh_button_click(), width=80)
refresh_button.pack(side="right", padx=5)

current_weather_frame = ctk.CTkFrame(master=app)
current_weather_frame.pack(pady=10, padx=10, fill="x")

weather_icon_label = ctk.CTkLabel(master=current_weather_frame, text="")
weather_icon_label.pack(side="left", padx=20, pady=10)

details_frame = ctk.CTkFrame(master=current_weather_frame)
details_frame.pack(side="left", padx=10, pady=10, expand=True, fill="both")

temp_label = ctk.CTkLabel(master=details_frame, text="気温: --℃ / 最高:--℃ 最低:--℃", font=("Arial", 18))
temp_label.pack(anchor="w")

feels_like_label = ctk.CTkLabel(master=details_frame, text="体感気温: --℃", font=("Arial", 14))
feels_like_label.pack(anchor="w")

humidity_label = ctk.CTkLabel(master=details_frame, text="湿度: --%", font=("Arial", 14))
humidity_label.pack(anchor="w")

pressure_label = ctk.CTkLabel(master=details_frame, text="気圧: --hPa", font=("Arial", 14))
pressure_label.pack(anchor="w")

wind_label = ctk.CTkLabel(master=details_frame, text="風速: --m/s", font=("Arial", 14))
wind_label.pack(anchor="w")

description_label = ctk.CTkLabel(master=details_frame, text="天気: ----", font=("Arial", 14))
description_label.pack(anchor="w")

hourly_forecast_outer_frame = ctk.CTkFrame(master=app)
hourly_forecast_outer_frame.pack(pady=(10, 10), padx=10, fill="x")

hourly_title_label = ctk.CTkLabel(master=hourly_forecast_outer_frame, text="時間ごとの予報:", font=("Arial", 16, "bold"))
hourly_title_label.pack(anchor="w", pady=(5, 10))

hourly_forecast_inner_frame = ctk.CTkFrame(master=hourly_forecast_outer_frame, fg_color="transparent")
hourly_forecast_inner_frame.pack(fill="x")

# 緑ちゃんのコメントと画像用のフレーム
midori_frame = ctk.CTkFrame(master=app)
midori_frame.pack(pady=(10, 20), padx=10, fill="x")

# 緑ちゃんのコメント表示用ラベル
midori_comment_label = ctk.CTkLabel(master=midori_frame, text="緑ちゃん: 今日も元気に楽しもうね！", font=("Arial", 14, "italic"), wraplength=600)
midori_comment_label.pack(side="left", padx=10)

# 緑ちゃんの画像表示用ラベル
midori_icon_label = ctk.CTkLabel(master=midori_frame, text="")
midori_icon_label.pack(side="right", padx=10)

# 緑ちゃんの画像を初期状態で読み込む
midori_icon = load_midori_icon(size=(100, 100))
if midori_icon:
    midori_icon_label.configure(image=midori_icon)
else:
    midori_icon_label.configure(text="画像読み込み失敗")

# --- 時間ごとの予報ウィジェットを作成する関数 ---
def create_hourly_forecasts(forecast_data):
    global hourly_weather_icons
    
    for widget in hourly_forecast_inner_frame.winfo_children():
        widget.destroy()
    
    hourly_weather_icons = []
    
    if not forecast_data or "list" not in forecast_data or not forecast_data["list"]:
        return
    
    forecast_items = forecast_data["list"]
    current_time = datetime.now()
    
    selected_forecasts = []
    for item in forecast_items:
        dt_txt = item.get("dt_txt", "")
        if not dt_txt:
            continue
        try:
            forecast_time = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S")
            time_diff = (forecast_time - current_time).total_seconds() / 3600
            if 0 <= time_diff <= 9:
                selected_forecasts.append((item, time_diff))
        except ValueError:
            continue
    
    selected_forecasts.sort(key=lambda x: x[1])
    selected_forecasts = [item for item, _ in selected_forecasts[:NUM_HOURLY_FORECASTS]]
    
    for item in selected_forecasts:
        frame = ctk.CTkFrame(master=hourly_forecast_inner_frame, width=120, height=150)
        frame.pack(side="left", padx=5, pady=5, fill="y", expand=True)
        
        dt_txt = item.get("dt_txt", "")
        time_str = "--:--"
        if dt_txt:
            try:
                time_str = datetime.strptime(dt_txt, "%Y-%m-%d %H:%M:%S").strftime("%H:%M")
            except ValueError:
                pass
        
        time_label = ctk.CTkLabel(master=frame, text=time_str, font=("Arial", 12))
        time_label.pack(pady=(10, 0))
        
        icon_label = ctk.CTkLabel(master=frame, text="")
        icon_label.pack(pady=5)
        
        hourly_temp_val = item.get("main", {}).get("temp")
        temp_text = f"{hourly_temp_val:.0f}℃" if hourly_temp_val is not None else "--℃"
        temp_label = ctk.CTkLabel(master=frame, text=temp_text, font=("Arial", 12))
        temp_label.pack()
        
        pop_percentage = item.get("pop", 0) * 100
        pop_label = ctk.CTkLabel(master=frame, text=f"降水: {pop_percentage:.0f}%", font=("Arial", 10))
        pop_label.pack(pady=(0, 10))
        
        hourly_icon_id = item.get("weather", [{}])[0].get("icon")
        if hourly_icon_id:
            icon_img = load_weather_icon(hourly_icon_id, size=(50, 50))
            if icon_img:
                icon_label.configure(image=icon_img, text="")
                hourly_weather_icons.append(icon_img)
            else:
                icon_label.configure(text="IconX")
        else:
            icon_label.configure(text="")

# --- 天気情報を更新して表示するメインの関数 ---
def update_weather_display(postal_code=None, city="Tokyo"):
    global main_weather_icon
    
    location_label.configure(text="取得中...")
    temp_label.configure(text="気温: --℃ / 最高:--℃ 最低:--℃")
    feels_like_label.configure(text="体感気温: --℃")
    humidity_label.configure(text="湿度: --%")
    pressure_label.configure(text="気圧: --hPa")
    wind_label.configure(text="風速: --m/s")
    description_label.configure(text="天気: ----")
    midori_comment_label.configure(text="緑ちゃん: 今日も元気に楽しもうね！")
    
    lat, lon, location_name = None, None, None
    if postal_code and postal_code.strip():
        lat, lon, location_name = get_lat_lon_from_postal_code(postal_code)
    
    current_weather = get_current_weather_data(lat=lat, lon=lon, city_name=city if not lat else None)
    forecast = get_forecast_data(lat=lat, lon=lon, city_name=city if not lat else None)
    
    if current_weather:
        if location_name and lat and lon:
            country_code = "JP"
            location_label.configure(text=f"{location_name}, {country_code}")
        else:
            actual_city_name = current_weather.get("name", "不明な都市")
            country_code = current_weather.get("sys", {}).get("country", "")
            location_label.configure(text=f"{actual_city_name}, {country_code}")
        
        main_data = current_weather.get("main", {})
        current_temp = main_data.get("temp")
        
        min_temp_today, max_temp_today = None, None
        if forecast and "list" in forecast:
            min_temp_today, max_temp_today = get_today_min_max_temps(forecast["list"])
        
        temp_text = f"気温: {current_temp:.1f}℃" if current_temp is not None else "気温: --℃"
        temp_text += f" / 最高:{max_temp_today:.1f}℃" if max_temp_today is not None else " / 最高:--℃"
        temp_text += f" 最低:{min_temp_today:.1f}℃" if min_temp_today is not None else " 最低:--℃"
        temp_label.configure(text=temp_text)
        
        feels_like = main_data.get("feels_like")
        if feels_like is not None:
            feels_like_label.configure(text=f"体感気温: {feels_like:.1f}℃")
        
        humidity = main_data.get("humidity")
        if humidity is not None:
            humidity_label.configure(text=f"湿度: {humidity}%")
        
        pressure = main_data.get("pressure")
        if pressure is not None:
            pressure_label.configure(text=f"気圧: {pressure}hPa")
        
        wind_data = current_weather.get("wind", {})
        wind_speed = wind_data.get("speed")
        if wind_speed is not None:
            wind_label.configure(text=f"風速: {wind_speed}m/s")
        
        weather_desc_data = current_weather.get("weather", [{}])[0]
        description = weather_desc_data.get("description", "----")
        description_label.configure(text=f"天気: {description}")
        
        # 緑ちゃんのコメントを生成
        if description != "----" and current_temp is not None:
            comment = get_midori_comment(description, current_temp)
            midori_comment_label.configure(text=f"緑ちゃん: {comment}")
        
        icon_id = weather_desc_data.get("icon")
        if icon_id:
            new_icon = load_weather_icon(icon_id, size=(100, 100))
            if new_icon:
                main_weather_icon = new_icon
                weather_icon_label.configure(image=main_weather_icon, text="")
            else:
                weather_icon_label.configure(image=None, text="Icon Err")
        else:
            weather_icon_label.configure(image=None, text="No Icon")
    else:
        location_label.configure(text="情報取得失敗")
        weather_icon_label.configure(image=None, text="No Data")
    
    create_hourly_forecasts(forecast)

# --- 自動更新用の関数 ---
def schedule_weather_update():
    postal_code = postal_code_entry.get()
    update_weather_display(postal_code=postal_code, city="Tokyo")
    app.after(3600000, schedule_weather_update)

# --- リフレッシュボタンのイベントハンドラ ---
def on_refresh_button_click():
    postal_code = postal_code_entry.get()
    update_weather_display(postal_code=postal_code, city="Tokyo")

# --- アプリ起動時に最初の情報表示と自動更新の開始 ---
update_weather_display(city="Tokyo")
schedule_weather_update()

# --- メインループの開始 ---
app.mainloop()