# Scripted text
Trigger hotkey get scripted text effect + sound  
For windows install [python3.6](https://www.python.org/downloads/release/python-368/) 64 or 32 bit depending on your OBS 
# Usage
Create text source.
_Optionally create media source_  
- Open `Tools>Scripts`
- select this script 
- set settings for it, change duration and refresh rate
- preview it if needed,
- reset if needed,
- set hotkey in `File>Settings`

If you need additional effects , copy paste `scripted_text.py` , and add it again.
# Example text effects
- static 
> just show text  
> cycle threw colors   
- ![preview](https://i.imgur.com/GmhEDv4.gif)   
> blinking text   
- ![preview](https://i.imgur.com/2M2wDUD.gif)   
> loading text  
- ![preview](https://i.imgur.com/H0pgtHf.gif)   
> tremor effect     
- ![preview](https://i.imgur.com/8G3TVGp.gif)   
> sanic effect    
- ![preview](https://i.imgur.com/pvaEWlE.gif)
# How it works
 There is two classes:
 - `TextContent` - updates text 
 - `Driver` - interacts with obs properties and controls execution

 Interaction with obs happens on instance of `Driver` - *std* it will update source name, scirpted text, selected effect and more according to settings from UI. Hotkey handling via `script_save` and `script_load` with callback on *std* `hotkey_hook`. Note: this callback is also attached to `PREVIEW` button in settings. It will trigger `obs_timer` , set `lock` to `False` (to run single callback at time).  `obs_timer` will execute `ticker` with `interval` aka `refresh_rate`. `ticker` will execute selected text effect from settings ,substract `refresh_rate` from `duration` , check if its <= 0,then reset everything to initial state,remove itself via `obs.remove_current_callback`. 
 To create a text effect , this naming `someefect_effect` is required. Text effects use inherited method  `update_text` to update text one tick at time. 

# Contribute 
[Forks](https://help.github.com/articles/fork-a-repo) are a great way to contribute to a repository.
After forking a repository, you can send the original author a [pull request](https://help.github.com/articles/using-pull-requests)
