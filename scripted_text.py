import string
import obspython as obs
from itertools import cycle
from functools import partial
from random import choice
from contextlib import contextmanager
from random import seed

__author__ = "upgradeQ"
__version__ = "0.5.0"
HOTKEY_ID = obs.OBS_INVALID_HOTKEY_ID

# auto release context managers
@contextmanager
def source_ar(source_name):
    source = obs.obs_get_source_by_name(source_name)
    try:
        yield source
    finally:
        obs.obs_source_release(source)


@contextmanager
def data_ar(source_settings=None):
    if not source_settings:
        settings = obs.obs_data_create()
    if source_settings:
        settings = obs.obs_source_get_settings(source_settings)
    try:
        yield settings
    finally:
        obs.obs_data_release(settings)


@contextmanager
def scene_ar(scene):
    scene = obs.obs_scene_from_source(scene)
    try:
        yield scene
    finally:
        obs.obs_scene_release(scene)


@contextmanager
def filter_ar(source, name):
    source = obs.obs_source_get_filter_by_name(source, name)
    try:
        yield source
    finally:
        obs.obs_source_release(source)


class TextContent:
    def __init__(self, text_string="This is default text", source_name=None):
        self.source_name = source_name
        self.text_string = text_string
        self.location = (0, 0)
        self._text_chars = self._wpm_chars = []
        self.rand_index = self.lst_index = self.wpm_index = 0
        self.position_swap = cycle([True, False])
        self.last_jump_x = self.last_jump_y = 0
        self.blinking = cycle([True, False])
        self.palette = cycle([0xFFBE0B, 0xFB5607, 0xFF006E, 0x8338EC, 0x3A86FF])
        self.dots = cycle([" ", ".", "..", "..."])

    def update_text(self, scripted_text, color=None):
        """takes scripted_text , sets its value in obs  """
        with source_ar(self.source_name) as source, data_ar() as settings:
            self.text_string = scripted_text
            if color:
                obs.obs_data_set_int(settings, "color", color)  # colored text
            obs.obs_data_set_string(settings, "text", self.text_string)
            obs.obs_source_update(source, settings)


class Driver(TextContent):
    def __init__(self, text_string, source_name):
        super().__init__(text_string, source_name)
        self.scripted_text = "default value"
        self.sound_source_name = None
        self.effect = "static"  # take value from property
        self.txt_efcts = self.load()

        self.lock = True
        self.refresh_rate = 250
        self.duration = 5 * 1000
        self.effect_duration = 3 * 1000

    def load(self):
        mapping = dict()
        effects_list = [
            "rainbow",
            "static",
            "blink",
            "loading",
            "tremor",
            "sanic",
            "typewriter",
            "scrmbl",
            "fastread",
        ]
        for i in effects_list:
            mapping[i] = getattr(self, i + "_" + "effect")
        return mapping

    def play_sound(self):
        with source_ar(self.sound_source_name) as source:
            obs.obs_source_media_restart(source)

    def stop_sound(self):
        with source_ar(self.sound_source_name) as source:
            obs.obs_source_media_stop(source)

    def ticker(self, text_effect):
        """ main time primitive """
        # effects updated every self.refresh_rate ms
        def check_duration():
            if self.duration <= 0:
                self.update_text("")
                obs.remove_current_callback()
                self.duration = 5 * 1000
                self.lock = True
                self.last_jump_y, self.last_jump_x = 0, 0
                self.lst_index = self.rand_index = self.wpm_index = 0

        try:
            self.txt_efcts[text_effect]()
            self.duration -= self.refresh_rate
            check_duration()

        except KeyError:
            self.duration = 0
            check_duration()
            raise Exception(f"No such effect: {text_effect}")

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

    def tremor_effect(self):

        flag = next(self.position_swap)
        if flag:
            self.update_text(self.scripted_text)
            current_scene = obs.obs_frontend_get_current_scene()
            with source_ar(self.source_name) as source, scene_ar(
                current_scene
            ) as scene:
                scene_item = obs.obs_scene_find_source(scene, self.source_name)
                pos = obs.vec2()
                self.location = pos
                obs.obs_sceneitem_get_pos(
                    scene_item, self.location
                )  # update to last position if its changed from OBS

                if not self.last_jump_x == 0:
                    if self.last_jump_x < 0:
                        # minus minus
                        self.location.x -= self.last_jump_x
                    if self.last_jump_x > 0:
                        self.location.x -= self.last_jump_x

                if not self.last_jump_y == 0:
                    if self.last_jump_y < 0:
                        self.location.y -= self.last_jump_y
                    if self.last_jump_y > 0:
                        self.location.y -= self.last_jump_y

                if scene_item:
                    obs.obs_sceneitem_set_pos(scene_item, self.location)

        else:
            self.update_text(self.scripted_text)
            current_scene = obs.obs_frontend_get_current_scene()
            with source_ar(self.source_name) as source, scene_ar(
                current_scene
            ) as scene:
                scene_item = obs.obs_scene_find_source(scene, self.source_name)
                pos = obs.vec2()
                self.location = pos
                obs.obs_sceneitem_get_pos(
                    scene_item, self.location
                )  # update to last position if its changed from OBS

                if scene_item:
                    # finish early , and set to default
                    if self.duration // self.refresh_rate <= 3:
                        self.duration = 0
                        obs.obs_sceneitem_set_pos(scene_item, self.location)

                    else:
                        next_pos = obs.vec2()
                        withoutzero = list(range(-101, 0)) + list(range(1, 101))
                        self.last_jump_x = choice(withoutzero)
                        self.last_jump_y = choice(withoutzero)
                        dx, dy = self.last_jump_x, self.last_jump_y
                        next_pos.x, next_pos.y = (
                            self.location.x + dx,
                            self.location.y + dy,
                        )
                        obs.obs_sceneitem_set_pos(scene_item, next_pos)

    def sanic_effect(self):
        # add filter scroll to source if not present,
        self.update_text(self.scripted_text)
        with source_ar(self.source_name) as source, filter_ar(
            source, "py_scroll"
        ) as scroll:
            if scroll is None:
                with data_ar() as settings:
                    obs.obs_data_set_int(settings, "speed_x", 5000)

                    source_scroll = obs.obs_source_create_private(
                        "scroll_filter", "py_scroll", settings
                    )
                    obs.obs_source_filter_add(source, source_scroll)
                    obs.obs_source_release(source_scroll)

            with data_ar(scroll) as filter_settings:
                obs.obs_data_set_int(filter_settings, "speed_x", 5000)
                obs.obs_source_update(scroll, filter_settings)
                if self.duration // self.refresh_rate <= 3:
                    obs.obs_source_filter_remove(source, scroll)
                    self.duration = 0

    def typewriter_effect(self):
        """adjust refresh rate in settings"""
        l = len(self.scripted_text)
        result = self.scripted_text[: self.lst_index]
        space_count = l - len(result)
        result += space_count * " "
        self.lst_index += 1
        self.update_text(result)

    def scrmbl_effect(self):
        """adjust refresh rate in settings"""
        try:
            self._text_chars = list(self.text_chars(self.scripted_text))
            self.update_text(self._text_chars[self.rand_index])
            self.rand_index += 1
        except IndexError:
            self.update_text(self.scripted_text)

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

        return gen(scripted_str, 3)

    def fastread_effect(self):
        """show one word at time centered with spaces"""
        try:
            self._wpm_chars = self.wpm_chars()
            self.update_text(self._wpm_chars[self.wpm_index])
            self.wpm_index += 1
        except IndexError:
            self.update_text("")

    def wpm_chars(self):
        s = self.scripted_text.split(" ")
        m = len(max(s, key=len))
        return [i.center(m, " ") for i in s]

    def hotkey_hook(self):
        """ trigger hotkey event"""
        self.play_sound()
        self.duration = self.effect_duration
        print("effect duration ", self.duration)
        interval = self.refresh_rate
        if self.lock:
            self.ticker = partial(self.ticker, text_effect=self.effect)
            obs.timer_add(self.ticker, interval)
        self.lock = False

    def reset_duration(self):
        self.duration = 0


scripted_text_driver = Driver(
    text_string="default string", source_name="default source name"
)


def script_description():
    return " Scripted text \n with effects and media ".upper()


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

    scripted_text_driver.effect_duration = obs.obs_data_get_int(settings, "duration")
    scripted_text_driver.sound_source_name = obs.obs_data_get_string(
        settings, "playsound"
    )
    scripted_text_driver.effect = obs.obs_data_get_string(settings, "text_effect")
    scripted_text_driver.stop_sound()


def script_properties():
    props = obs.obs_properties_create()

    obs.obs_properties_add_text(
        props, "scripted_text", "Scripted text", obs.OBS_TEXT_DEFAULT
    )
    obs.obs_properties_add_int(
        props, "refresh_rate", "Refresh rate(ms)", 15, 5 * 1000, 1
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

    for i in scripted_text_driver.txt_efcts.keys():
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

        obs.source_list_release(sources)

    obs.obs_properties_add_button(
        props, "button1", "PREVIEW", lambda *props: scripted_text_driver.hotkey_hook()
    )

    obs.obs_properties_add_button(
        props, "button2", "RESET", lambda *props: scripted_text_driver.reset_duration()
    )

    return props


def script_save(settings):
    global HOTKEY_ID
    hotkey_save_array = obs.obs_hotkey_save(HOTKEY_ID)
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
    hotkey_save_array = obs.obs_data_get_array(settings, "scripted_text_hotkey")
    obs.obs_hotkey_load(HOTKEY_ID, hotkey_save_array)
    obs.obs_data_array_release(hotkey_save_array)
