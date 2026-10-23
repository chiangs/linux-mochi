-- Mochi on Hyprland 0.55+ (Lua config): paste into ~/.config/hypr/hyprland.lua

-- frosted glass behind her pill and pop-ups (then set "glass_alpha": 0.7 in ~/.local/share/mochi/config.json)
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
