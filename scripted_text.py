"""
Related code for text sources 
gdi:
https://github.com/obsproject/obs-studio/blob/master/plugins/obs-text/gdiplus/obs-text.cpp
freetype2:
https://github.com/obsproject/obs-studio/blob/master/plugins/text-freetype2/text-freetype2.c
"""
__author__ = "upgradeQ"
__version__ = "1.0.0"
__licence__ = "MPL-2.0"

import string
import obspython as obs
from ast import literal_eval
from itertools import cycle
from functools import partial
from random import choice, randrange
from contextlib import contextmanager
from pathlib import Path
from random import seed
from datetime import timedelta
from string import Template


# auto release context managers
@contextmanager
def source_ar(source_name):
    source = obs.obs_get_source_by_name(source_name)
    try:
        yield source
    finally:
        obs.obs_source_release(source)


@contextmanager
def p_source_ar(id, source_name, settings):
    try:
        _source = obs.obs_source_create_private(id, source_name, settings)
        yield _source
    finally:
        obs.obs_source_release(_source)


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
    source_name = None
    text_string = ""

    def __init__(self):
        self.location = (0, 0)
        self._text_chars = self._wpm_chars = []
        self.rand_index = self.lst_index = self.wpm_index = self.lst_rev = 0
        self.position_swap = cycle([True, False])
        self.last_jump_x = self.last_jump_y = 0
        self.blinking = cycle([True, False])
        self.default_palette = [0xFFBE0B, 0xFB5607, 0xFF006E, 0x8338EC, 0x3A86FF]
        self.palette = cycle(self.default_palette)
        self.dots = cycle([" ", ".", "..", "..."])

    def update_text(self, scripted_text, color=None):
        """takes scripted_text , sets its value in obs  """
        with source_ar(self.source_name) as source, data_ar() as settings:
            self.text_string = scripted_text
            if color:
                self.set_color(color, settings)
            obs.obs_data_set_string(settings, "text", self.text_string)
            obs.obs_source_update(source, settings)

    def set_color(self, color, settings):
        if self._obs_source_type == "text_gdiplus":
            obs.obs_data_set_int(settings, "color", color)  # colored text

        else:  # freetype2,if taken from user input it should be reversed for getting correct color
            if not color in self.default_palette:
                number = "".join(reversed(hex(color)[2:]))
            else:
                number = "".join(hex(color)[2:])
            color = int("0xff" f"{number}", base=16)
            obs.obs_data_set_int(settings, "color1", color)
            obs.obs_data_set_int(settings, "color2", color)

    @property
    def _obs_source_type(self):
        with source_ar(self.source_name) as source:
            return obs.obs_source_get_unversioned_id(source)

    def clear_text_content(self):
        if self._obs_source_type == "text_ft2_source":
            self.update_text(" ")
        if self._obs_source_type == "text_gdiplus":
            self.update_text("")
        if self._obs_source_type is None:
            self.update_text(" ")


class Driver(TextContent):
    def __init__(self):
        super().__init__()
        self.scripted_text = "default value"
        self.sound_source_name = None
        self.layer_source_name = None
        self.effect = "static"
        self.use_file = False
        self.reload_file = False
        self.path = str(Path.home())
        self.file_path = ""
        self.txt_efcts = self.load()

        self.first_run = True  # text effect
        self.lock = True  # ticker
        self.start = True  # media source & layer source
        self.refresh_rate = 250
        self.duration = 5
        self.effect_duration = 3

    def load(self):
        mapping = dict()
        effects_list = []
        for i in dir(self):
            if "effect" in i:
                try:
                    if i.split("_")[1] == "effect":
                        effects_list.append(i.split("_")[0])
                except IndexError:
                    continue
        for i in effects_list:
            mapping[i] = getattr(self, i + "_" + "effect")
        return mapping

    def read_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                return content
        except Exception as e:
            print("error reading file", e)
            return "error"

    @property
    def _scripted_text(self):
        if self.use_file and self.reload_file:
            return self.read_file(self.file_path)
        return self.scripted_text

    def play_sound(self):
        with source_ar(self.sound_source_name) as source:
            obs.obs_source_media_restart(source)

    def stop_sound(self):
        with source_ar(self.sound_source_name) as source:
            obs.obs_source_media_stop(source)

    def enable_layer(self):
        with source_ar(self.layer_source_name) as source:
            obs.obs_source_set_enabled(source, True)

    def disable_layer(self):
        with source_ar(self.layer_source_name) as source:
            obs.obs_source_set_enabled(source, False)

    def synchronized_start(self):
        if self.start:
            self.play_sound()
            self.enable_layer()
            self.start = False

    def ticker(self, text_effect):
        """ main time primitive """
        # effects updated every self.refresh_rate ms
        def check_duration():
            if self.duration <= 0:
                self.clear_text_content()
                self.disable_layer()
                obs.remove_current_callback()
                self.duration = 5 * 1000
                self.lock = self.first_run = self.start = True
                self.last_jump_y, self.last_jump_x = 0, 0
                self.lst_index = self.rand_index = self.wpm_index = self.lst_rev = 0

        try:
            self.synchronized_start()
            self.txt_efcts[text_effect]()
            self.duration -= self.refresh_rate
            check_duration()

        except KeyError:
            self.duration = 0
            check_duration()
            raise Exception(f"No such effect: {text_effect}")

    def static_effect(self):
        "just show text "
        self.update_text(self._scripted_text)

    def rainbow_effect(self):
        """cycle threw default palette or provide yours.Syntax:
            scripted text;0xff00ff,0x00ff,etc"""
        if ";" in self._scripted_text:
            if self.first_run:
                res = self._scripted_text.split(";")[1].split(",")
                self._text = self._scripted_text.split(";")[0]
                colors = []
                for i in res:
                    try:
                        color = literal_eval(i)
                        colors.append(color)
                    except Exception as e:
                        print(e)
                        continue

                if len(colors) > 0:
                    self.user_palette = cycle(colors)
                else:
                    self.user_palette = self.palette

                self.first_run = False
                self.update_text(self._text, color=next(self.user_palette))
            else:
                self.update_text(self._text, color=next(self.user_palette))

        else:
            self.update_text(self._scripted_text, color=next(self.palette))

    def blink_effect(self):
        "on and off"
        flag = next(self.blinking)
        if flag:
            self.update_text(self._scripted_text)
        else:
            self.clear_text_content()

    def loading_effect(self):
        "dots..."
        self.update_text(self._scripted_text + next(self.dots))

    def tremor_effect(self):
        "random movements in range(-100,100)[current scene only]"
        flag = next(self.position_swap)
        if flag:
            self.update_text(self._scripted_text)
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
            self.update_text(self._scripted_text)
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
        "really fast speed text scrolling(filter)"
        # add filter scroll to source if not present,
        self.update_text(self._scripted_text)
        with source_ar(self.source_name) as source, filter_ar(
            source, "py_scroll"
        ) as scroll:
            if scroll is None:
                with data_ar() as settings:
                    obs.obs_data_set_int(settings, "speed_x", 5000)
                    with p_source_ar("scroll_filter", "py_scroll", settings) as _source:
                        obs.obs_source_filter_add(source, _source)

            with data_ar(scroll) as filter_settings:
                obs.obs_data_set_int(filter_settings, "speed_x", 5000)
                obs.obs_source_update(scroll, filter_settings)
                if self.duration // self.refresh_rate <= 3:
                    obs.obs_source_filter_remove(source, scroll)
                    self.duration = 0

    def typewriter_effect(self):
        """simulate typing"""
        l = len(self._scripted_text)
        result = self._scripted_text[: self.lst_index]
        space_count = l - len(result)
        result += space_count * " "
        self.lst_index += 1
        self.update_text(result)

    def scrmbl_effect(self):
        """random chars revealing"""
        try:
            self._text_chars = list(self.text_chars(self._scripted_text))
            self.update_text(self._text_chars[self.rand_index])
            self.rand_index += 1
        except IndexError:
            self.update_text(self._scripted_text)

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
        """show one word at time separate with ";"
        """
        try:
            self._wpm_chars = self.wpm_chars()
            self.update_text(self._wpm_chars[self.wpm_index])
            self.wpm_index += 1
        except IndexError:
            self.clear_text_content()

    def wpm_chars(self):
        s = self._scripted_text.split(";")
        m = len(max(s, key=len))
        return [i.center(m, " ") for i in s]

    def timer_effect(self):
        """ timer syntax "seconds = $s , centisecond = $cs"
        """
        m_s = self.duration
        d = timedelta(milliseconds=m_s)
        s = d.seconds
        cs = str(d.microseconds)[:2]
        n = self._scripted_text
        ts = Template(n)
        try:
            time_data = ts.substitute(s=s, cs=cs)
            self.update_text(time_data)
        except:  # skip errors when  incorrect substitition happens
            self.update_text(self._scripted_text)

    def hue_effect(self):
        "apply random hue,add second color to see the effect"
        self.update_text(self._scripted_text)
        with source_ar(self.source_name) as source, filter_ar(source, "py_hue") as hue:
            if hue is None:
                with data_ar() as settings:
                    with p_source_ar("color_filter", "py_hue", settings) as _source:
                        obs.obs_source_filter_add(source, _source)

            with data_ar(hue) as filter_settings:
                seed()
                n = randrange(-180, 180)
                obs.obs_data_set_int(filter_settings, "hue_shift", n)
                obs.obs_source_update(hue, filter_settings)
                if self.duration // self.refresh_rate <= 3:
                    obs.obs_source_filter_remove(source, hue)
                    self.duration = 0

    def fade_effect(self):
        "fade text via opacity filter"
        self.update_text(self._scripted_text)
        with source_ar(self.source_name) as source, filter_ar(
            source, "py_fade"
        ) as fade:

            if fade is None:
                with data_ar() as settings:
                    with p_source_ar("color_filter", "py_fade", settings) as _source:
                        obs.obs_source_filter_add(source, _source)

            with data_ar(fade) as filter_settings:
                try:
                    coefficient = self.effect_duration / self.duration
                    percent = 100 / coefficient
                except ZeroDivisionError:
                    percent = 0
                obs.obs_data_set_int(filter_settings, "opacity", int(percent))
                obs.obs_source_update(fade, filter_settings)
                if self.duration // self.refresh_rate <= 3:
                    obs.obs_source_filter_remove(source, fade)
                    self.duration = 0

    def percent_effect(self):
        """ percent syntax "sample text $pc"
        """
        try:
            coefficient = self.effect_duration / self.duration
            percent = 100 / coefficient
        except ZeroDivisionError:
            percent = 0
        n = self._scripted_text
        ts = Template(n)
        try:
            percent_time = ts.substitute(pc=f"{percent:.2f}%")
            self.update_text(percent_time)
        except:  # skip errors when  incorrect substitition happens
            self.update_text(self._scripted_text)

    def erase_effect(self):
        "similiar to typewriter, but erase and start with new string, separate with ;"

        if self.first_run:
            self.splitted_text = cycle(self._scripted_text.split(";"))
            self.next_string = next(self.splitted_text)
            self.first_run = False

        l = len(self.next_string)
        result = self.next_string[: self.lst_index]
        space_count = l - len(result)
        result += space_count * " "
        self.lst_index += 1
        if self.lst_index > l:
            result = (
                self.next_string[: -self.lst_rev]
                if self.lst_rev != 0
                else self.next_string  # keep last character
            )
            self.lst_rev += 1
            if self.lst_rev > l:
                self.lst_index = 0
                self.next_string = next(self.splitted_text)
            self.update_text(result)
        else:
            self.lst_rev = 0
            self.update_text(result)

    def hotkey_hook(self):
        """ trigger hotkey event"""
        self.duration = self.effect_duration
        interval = self.refresh_rate
        if self.lock:
            self.ticker = partial(self.ticker, text_effect=self.effect)
            obs.timer_add(self.ticker, interval)
        self.lock = False

    def reset_duration(self):
        self.duration = 0


class Hotkey:
    def __init__(self, callback, obs_settings, _id):
        self.obs_data = obs_settings
        self.hotkey_id = obs.OBS_INVALID_HOTKEY_ID
        self.hotkey_saved_key = None
        self.callback = callback
        self._id = _id

        self.load_hotkey()
        self.register_hotkey()
        self.save_hotkey()

    def register_hotkey(self):
        description = "Htk " + str(self._id)
        self.hotkey_id = obs.obs_hotkey_register_frontend(
            "htk_id" + str(self._id), description, self.callback
        )
        obs.obs_hotkey_load(self.hotkey_id, self.hotkey_saved_key)

    def load_hotkey(self):
        self.hotkey_saved_key = obs.obs_data_get_array(
            self.obs_data, "htk_id" + str(self._id)
        )
        obs.obs_data_array_release(self.hotkey_saved_key)

    def save_hotkey(self):
        self.hotkey_saved_key = obs.obs_hotkey_save(self.hotkey_id)
        obs.obs_data_set_array(
            self.obs_data, "htk_id" + str(self._id), self.hotkey_saved_key
        )
        obs.obs_data_array_release(self.hotkey_saved_key)


class h:
    htk_copy = None  # this attribute will hold instance of Hotkey


std = Driver()
h1 = h()
h2 = h()


def trigger(pressed):
    if pressed:
        return std.hotkey_hook()


def reset(pressed):
    if pressed:
        return std.reset_duration()


def script_description():
    s = '<a href="https://obsproject.com/forum/resources/scripted-text.988/">FORUM</a>'
    return "<h1>Scripted text</h1> \n <h2>with effects and media</h2> " + s


def show_tooltip(props, prop, settings):
    p = obs.obs_properties_get(props, "text_effect")
    docs = getattr(std, std.effect + "_effect", "default")
    if docs == "default":
        selection = "[error]: there is no such effect".upper()
        color = "red"
    else:
        selection = docs.__doc__
        color = "green"
    styled_docs = f'<h1 style="color:{color};">{selection}</h1>'
    obs.obs_property_set_long_description(p, styled_docs)
    return True


def check_file_use(props, prop, settings):
    p = obs.obs_properties_get(props, "file_path")
    st = obs.obs_properties_get(props, "scripted_text")
    p2 = obs.obs_properties_get(props, "reload_file")
    obs.obs_property_set_visible(p, std.use_file)
    obs.obs_property_set_visible(p2, std.use_file)
    obs.obs_property_set_visible(st, not std.use_file)
    return True


def script_defaults(settings):
    obs.obs_data_set_default_int(settings, "refresh_rate", std.refresh_rate)
    obs.obs_data_set_default_int(settings, "duration", std.duration)
    obs.obs_data_set_default_string(settings, "scripted_text", std.scripted_text)
    obs.obs_data_set_default_string(settings, "text_effect", std.effect)


def script_update(settings):
    std.source_name = obs.obs_data_get_string(settings, "source")
    std.use_file = obs.obs_data_get_bool(settings, "use_file")
    std.reload_file = obs.obs_data_get_bool(settings, "reload_file")
    if not std.use_file:
        std.scripted_text = obs.obs_data_get_string(settings, "scripted_text")
    else:
        std.scripted_text = std.read_file(
            obs.obs_data_get_string(settings, "file_path")
        )
        std.file_path = obs.obs_data_get_string(settings, "file_path")
    std.effect = obs.obs_data_get_string(settings, "text_effect")
    std.refresh_rate = obs.obs_data_get_int(settings, "refresh_rate")
    std.effect_duration = 1000 * obs.obs_data_get_int(settings, "duration")

    std.sound_source_name = obs.obs_data_get_string(settings, "playsound")
    std.layer_source_name = obs.obs_data_get_string(settings, "layer")
    std.stop_sound()


def script_properties():
    props = obs.obs_properties_create()
    obs.obs_properties_add_text(
        props, "scripted_text", "Scripted text", obs.OBS_TEXT_MULTILINE
    )
    bool = obs.obs_properties_add_bool(props, "use_file", "Use file(UTF-8)")
    bool2 = obs.obs_properties_add_bool(props, "reload_file", "Auto reload file")

    fp = obs.obs_properties_add_path(
        props, "file_path", "Select file", obs.OBS_PATH_FILE, "*.*", std.path
    )

    obs.obs_property_set_visible(fp, std.use_file)
    obs.obs_property_set_visible(bool2, std.use_file)
    obs.obs_property_set_modified_callback(bool, check_file_use)
    obs.obs_property_set_modified_callback(bool2, check_file_use)
    obs.obs_properties_add_int(
        props, "refresh_rate", "Refresh rate(ms)", 15, 5 * 1000, 1
    )
    obs.obs_properties_add_int(props, "duration", "Duration shown(s)", 1, 3600, 1)

    p = obs.obs_properties_add_list(
        props,
        "source",
        "<h2>Text Source</h2>",
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

    lp = obs.obs_properties_add_list(
        props,
        "layer",
        "Layer(img,video,gif,etc..)",
        obs.OBS_COMBO_TYPE_EDITABLE,
        obs.OBS_COMBO_FORMAT_STRING,
    )

    obs.obs_property_set_long_description(
        tp, "<h1>Description of current text effect</h1>"
    )

    for i in std.txt_efcts.keys():
        obs.obs_property_list_add_string(tp, i, i)
    obs.obs_property_set_modified_callback(tp, show_tooltip)

    sources = obs.obs_enum_sources()
    if sources is not None:
        for source in sources:
            # exclude Desktop Audio and Mic/Aux by their capabilities
            capability_flags = obs.obs_source_get_output_flags(source)
            if (
                capability_flags & obs.OBS_SOURCE_DO_NOT_SELF_MONITOR
            ) == 0 and capability_flags != (
                obs.OBS_SOURCE_AUDIO | obs.OBS_SOURCE_DO_NOT_DUPLICATE
            ):
                source_id = obs.obs_source_get_unversioned_id(source)
                if source_id == "text_gdiplus" or source_id == "text_ft2_source":
                    name = obs.obs_source_get_name(source)
                    obs.obs_property_list_add_string(p, name, name)
                if source_id == "ffmpeg_source":
                    name = obs.obs_source_get_name(source)
                    obs.obs_property_list_add_string(sp, name, name)
                else:
                    name = obs.obs_source_get_name(source)
                    obs.obs_property_list_add_string(lp, name, name)

        obs.source_list_release(sources)

    scenes = obs.obs_frontend_get_scenes()  # for layered scene source
    for scene in scenes:
        name = obs.obs_source_get_name(scene)
        obs.obs_property_list_add_string(lp, name, name)
    obs.source_list_release(scenes)

    obs.obs_properties_add_button(
        props, "button1", "PREVIEW", lambda *props: std.hotkey_hook()
    )

    obs.obs_properties_add_button(
        props, "button2", "RESET", lambda *props: std.reset_duration()
    )

    return props


def script_save(settings):
    h1.htk_copy.save_hotkey()
    h2.htk_copy.save_hotkey()


def script_load(settings):
    h1.htk_copy = Hotkey(trigger, settings, "Trigger [scripted text]")
    h2.htk_copy = Hotkey(reset, settings, "Reset duration [scripted text]")
