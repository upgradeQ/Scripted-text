import obspython as obs
from itertools import cycle
from functools import partial
from time import sleep
import string

__author__ = "upgradeQ"
__version__ = "0.2.0"
HOTKEY_ID = obs.OBS_INVALID_HOTKEY_ID 

class TextContent:
    def __init__(self, text_string="This is default text", source_name=None):
        self.source_name = source_name
        self.text_string = text_string

    def update_text(self, scripted_text, color=None):
        """takes scripted_text , sets its value in obs  """
        source = obs.obs_get_source_by_name(self.source_name)
        settings = obs.obs_data_create()
        self.text_string = scripted_text
        if color:
            obs.obs_data_set_int(settings, "color", color)  # colored text
        obs.obs_data_set_string(settings, "text", self.text_string)
        obs.obs_source_update(source, settings)
        obs.obs_data_release(settings)
        obs.obs_source_release(source)


class Driver(TextContent):
    def __init__(self, text_string, source_name):
        super().__init__(text_string, source_name)
        self.scripted_text = "default value"
        self.sound_source_name = None
        self.effect = "static"  # take value from property

        self.lock = True
        self.refresh_rate = 250
        self.duration = 5 * 1000
        self.effect_duration = 3 * 1000

        self.blinking = cycle([True, False])
        self.palette = cycle([0xFFBE0B, 0xFB5607, 0xFF006E, 0x8338EC, 0x3A86FF])
        self.dots = cycle([" ", ".", "..", "..."])

    def play_sound(self):
        source = obs.obs_get_source_by_name(self.sound_source_name)
        obs.obs_source_media_restart(source)
        obs.obs_source_release(source)

    def stop_sound(self):
        source = obs.obs_get_source_by_name(self.sound_source_name)
        obs.obs_source_media_stop(source)
        obs.obs_source_release(source)

    def ticker(self, text_effect):
        """ main time primitive """
        # those effects updated every self.refresh_rate ms

        if text_effect == "static":
            self.static_effect()
        if text_effect == "blink":
            self.blink_effect()
        if text_effect == "rainbow":
            self.rainbow_effect()
        if text_effect == "loading":
            self.loading_effect()

        self.duration -= self.refresh_rate
        print(self.duration)
        if self.duration <= 0:
            self.update_text("")
            obs.remove_current_callback()
            self.duration = 5 * 1000
            self.lock = True

    def static_effect(self):
        self.update_text(self.scripted_text)

    def rainbow_effect(self):
        self.update_text(self.scripted_text, color=next(self.palette))

    def blink_effect(self):
        flag = next(self.blinking)
        if flag:
            self.update_text(self.scripted_text)
        else:
            self.update_text("")

    def loading_effect(self):
        self.update_text(self.scripted_text + next(self.dots))

    def hotkey_hook(self):
        """ trigger hotkey event"""
        self.play_sound()
        print("effect duration ", self.effect_duration)
        self.duration = self.effect_duration
        print("effect duration ", self.duration)
        interval = self.refresh_rate
        if self.lock:
            self.ticker = partial(self.ticker, text_effect=self.effect)
            obs.timer_add(self.ticker, interval)
        self.lock = False


scripted_text_driver = Driver(
    text_string="default string", source_name="default source name"
)

def script_description():
    return " Scripted text \n with effects and media "


def script_defaults(settings):
    obs.obs_data_set_default_int(
        settings, "refresh_rate", scripted_text_driver.refresh_rate
    )
    obs.obs_data_set_default_int(settings, "duration", scripted_text_driver.duration)


def script_update(settings):
    scripted_text_driver.source_name = obs.obs_data_get_string(settings, "source")

    scripted_text_driver.scripted_text = obs.obs_data_get_string(
        settings, "scripted_text"
    )
    scripted_text_driver.refresh_rate = obs.obs_data_get_int(settings, "refresh_rate")

    print("setting duration")
    scripted_text_driver.effect_duration = obs.obs_data_get_int(settings, "duration")
    scripted_text_driver.sound_source_name = obs.obs_data_get_string(
        settings, "playsound"
    )
    scripted_text_driver.effect = obs.obs_data_get_string(settings, "text_effect")
    print("stopping sound")
    scripted_text_driver.stop_sound()


def script_properties():
    "https://obsproject.com/docs/reference-properties.html"
    props = obs.obs_properties_create()

    obs.obs_properties_add_text(
        props, "scripted_text", "Scripted text", obs.OBS_TEXT_DEFAULT
    )
    obs.obs_properties_add_int(
        props, "refresh_rate", "Refresh rate(ms)", 50, 5 * 1000, 1
    )
    obs.obs_properties_add_int(
        props, "duration", "Duration shown(ms)", 1 * 1000, 3600 * 1000, 1
    )

    p = obs.obs_properties_add_list(
        props,
        "source",
        "Text Source",
        obs.OBS_COMBO_TYPE_EDITABLE,
        obs.OBS_COMBO_FORMAT_STRING,
    )
    sp = obs.obs_properties_add_list(
        props,
        "playsound",
        "Media Source",
        obs.OBS_COMBO_TYPE_EDITABLE,
        obs.OBS_COMBO_FORMAT_STRING,
    )
    tp = obs.obs_properties_add_list(
        props,
        "text_effect",
        "Text effect",
        obs.OBS_COMBO_TYPE_EDITABLE,
        obs.OBS_COMBO_FORMAT_STRING,
    )

    for i in ["rainbow", "static", "blink", "loading"]:
        obs.obs_property_list_add_string(tp, i, i)

    sources = obs.obs_enum_sources()
    if sources is not None:
        for source in sources:
            source_id = obs.obs_source_get_unversioned_id(source)
            if source_id == "text_gdiplus" or source_id == "text_ft2_source":
                name = obs.obs_source_get_name(source)
                obs.obs_property_list_add_string(p, name, name)
            if source_id == "ffmpeg_source":
                name = obs.obs_source_get_name(source)
                obs.obs_property_list_add_string(sp, name, name)
                print(name)

        obs.source_list_release(sources)

    obs.obs_properties_add_button(
        props, "button1", "preview", lambda *props: scripted_text_driver.hotkey_hook()
    )

    return props


def script_save(settings):
    global HOTKEY_ID
    hotkey_save_array = obs.obs_hotkey_save(HOTKEY_ID)
    print('htksave',hotkey_save_array)
    obs.obs_data_set_array(settings, "scripted_text_hotkey", hotkey_save_array)
    obs.obs_data_array_release(hotkey_save_array)


def script_load(settings):
    global HOTKEY_ID

    def callback_up(pressed):
        if pressed:
            return scripted_text_driver.hotkey_hook()

    HOTKEY_ID = obs.obs_hotkey_register_frontend(
        "scripted_text_hotkey", "Trigger sripted text", callback_up
    )
    obs.obs_data_get_array(settings, "scripted_text_hotkey")
    hotkey_save_array = obs.obs_data_get_array(settings, "scripted_text_hotkey")
    obs.obs_hotkey_load(HOTKEY_ID, hotkey_save_array)
    obs.obs_data_array_release(hotkey_save_array)
