-- Mochi on Hyprland 0.55+ (Lua config): paste into ~/.config/hypr/hyprland.lua

-- frosted glass behind her pill and pop-ups (then set "glass_alpha": 0.7 in ~/.config/mochi/config.json)
hl.layer_rule({
    name  = "mochi-blur",
    match = { namespace = "^mochi$" },
    blur  = true,
    ignore_alpha = 0.3,
})

-- start her with Hyprland (instead of "Open at Login", which needs an XDG-autostart runner like uwsm or dex)
hl.on("hyprland.start", function()
    hl.exec_cmd("mochi")
end)

-- a keyboard shortcut: Super+Alt+M opens her message bar, ready to type (pick any key you like)
hl.bind("SUPER + ALT + M", hl.dsp.exec_cmd("mochi --message"))
-- hl.bind("SUPER + ALT + T", hl.dsp.exec_cmd("mochi --todo"))     -- her to-do list
