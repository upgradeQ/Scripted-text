import obspython as obs
from itertools import cycle, repeat
from functools import partial
from random import choice, seed
from time import sleep
import string

__author__ = 'upgradeQ'
__version__ = '0.1.0'

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
        self.hotkey_id_scripted_text = obs.OBS_INVALID_HOTKEY_ID
        self.effect = "static"  # take value from property

        self.preview = True
        self.hide = False

        self.refresh_rate = 250
        self.duration = 5 * 1000
        self.effect_duration = 3 * 1000
        self.l = []
        self.i = 0

        self.blinking = cycle([True, False])
        self.palette = cycle([0xFFBE0B, 0xFB5607, 0xFF006E, 0x8338EC, 0x3A86FF])  # csv

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

        if text_effect == "static":
            self.static_effect()
        if text_effect == "blink":
            self.blink_effect()
        if text_effect == "rainbow":
            # self.refresh_rate = 50
            self.rainbow_effect()
        if text_effect == "random_chars":
            self.l = list(self.text_chars(self.scripted_text))
            self.random_effect()

        self.duration -= self.refresh_rate
        print(self.duration)
        if self.duration <= 0:
            self.update_text("")
            obs.remove_current_callback()
            self.duration = 5 * 1000
            self.preview = True
            self.hide = True

    # those effects updated every self.refresh_rate ms
    def static_effect(self):
        self.update_text(self.scripted_text)

    def rainbow_effect(self):
        self.update_text(self.scripted_text, color=next(self.palette))

    def blink_effect(self):
        print("inside blink")
        flag = next(self.blinking)
        if flag:
            self.update_text(self.scripted_text)
        else:
            self.update_text("")

    def random_effect(self):
        try:
            self.update_text(self.l[self.i])
            self.i += 1
        except IndexError:
            self.refresh_rate = 0
            self.update_text(self.scripted_text)
            sleep(1)  # sometimes causes to print additional characters after...
            # setting all to default
            self.i = 0
            self.refresh_rate = 250

    def text_chars(self, scripted_str):
        """inspired by https://github.com/etienne-napoleone/scrmbl """

        ALL_CHARS = string.digits + string.ascii_letters + string.punctuation

        def gen(scripted_str, iterations):
            seed()  # set new seed
            echoed = ""
            fill = len(scripted_str)
            for char in scripted_str:
                for _ in range(iterations):
                    if char != " ":
                        ran_char = choice(ALL_CHARS)
                        yield f"{echoed}{ran_char}{' '*fill}"
                    else:
                        yield f"{echoed}{' '*fill}"
                echoed += char
            if echoed:  # last char
                yield f"{echoed}"

        return gen(scripted_str, 5)

    def hotkey_hook(self):
        """ trigger hotkey event"""
        self.play_sound()
        self.duration = self.effect_duration
        print("effect duration ", self.duration)
        if self.effect == "random_chars":
            l = len(self.l)
            static_duration = 1
            try:
                t = (self.duration - static_duration) // l
                self.refresh_rate = t
            except ZeroDivisionError:  # startup bug
                self.refresh_rate = 50
        interval = self.refresh_rate
        if self.preview:
            self.ticker = partial(self.ticker, text_effect=self.effect)
            obs.timer_add(self.ticker, interval)
        self.preview = False

    def refresh_text(self):
        self.play_sound()
        """ trigger refresh button event"""
        self.duration = 5000
        self.refresh_rate = 250
        print("refresh pressed", repr(self.scripted_text))
        self.update_text(self.scripted_text)


scripted_text_driver = Driver(
    text_string="default string", source_name="default source name"
)


def refresh(prop, props):
    """ refresh button"""
    scripted_text_driver.refresh_text()
    interval = scripted_text_driver.refresh_rate
    effect = scripted_text_driver.effect
    print(effect)
    if scripted_text_driver.preview:
        scripted_text_driver.ticker = partial(
            scripted_text_driver.ticker, text_effect=effect
        )
        obs.timer_add(scripted_text_driver.ticker, interval)
    scripted_text_driver.preview = False


def script_description():
    return " Scripted text \n with effects and media "


def script_update(settings):
    scripted_text_driver.source_name = obs.obs_data_get_string(settings, "source")

    scripted_text_driver.scripted_text = obs.obs_data_get_string(
        settings, "scripted_text"
    )
    scripted_text_driver.refresh_rate = obs.obs_data_get_int(settings, "refresh_rate")

    print("setting duration")
    ed = scripted_text_driver.effect_duration = obs.obs_data_get_int(settings, "duration")
    if ed <=0:
        scripted_text_driver.effect_duration = 1000 # bug refresh rate not applied when not updated
    
    scripted_text_driver.sound_source_name = obs.obs_data_get_string(
        settings, "playsound"
    )
    scripted_text_driver.effect = obs.obs_data_get_string(settings, "text_effect")
    print('stopping sound')
    scripted_text_driver.stop_sound()


def script_save(settings):
    hotkey_save_array_scripted_text = obs.obs_hotkey_save(
        scripted_text_driver.hotkey_id_scripted_text
    )
    obs.obs_data_set_array(
        settings, "scripted_text_hotkey", hotkey_save_array_scripted_text
    )
    obs.obs_data_array_release(hotkey_save_array_scripted_text)


def script_properties():
    "https://obsproject.com/docs/reference-properties.html"
    props = obs.obs_properties_create()

    obs.obs_properties_add_text(
        props, "scripted_text", "Scripted text", obs.OBS_TEXT_DEFAULT
    )
    obs.obs_properties_add_int(props, "refresh_rate", "Refresh rate(ms)", 50, 5000, 1)
    obs.obs_properties_add_int(props, "duration", "Duration shown(ms)", 5000, 15000, 1)

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

    for i in ["rainbow", "static", "random_chars", "blink"]:
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

    obs.obs_properties_add_button(props, "button", "Refresh and preview(5s)", refresh)
    return props


def script_load(settings):
    def callback_up(pressed):
        if pressed:
            return scripted_text_driver.hotkey_hook()

    hotkey_id_scripted_text = obs.obs_hotkey_register_frontend(
        "Trigger sripted text", "Trigger sripted text", callback_up
    )
    hotkey_save_array_scripted_text = obs.obs_data_get_array(
        settings, "scripted_text_hotkey"
    )
    obs.obs_hotkey_load(hotkey_id_scripted_text, hotkey_save_array_scripted_text)
    obs.obs_data_array_release(hotkey_save_array_scripted_text)
