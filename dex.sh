#!/bin/bash
# https://github.com/nikp123/scrcpy-desktop

LAUNCHER_PACKAGE=com.farmerbb.taskbar
KEYBOARD_PACKAGE=com.wparam.nullkeyboard

enable_desktop_mode(){
    adb shell settings put global force_desktop_mode_on_external_displays 1
    adb shell settings put global force_allow_on_external 1
    adb shell settings put global overlay_display_devices none
    echo "Enabled desktop mode"

    adb shell sync
    sleep 2

    # You need to reboot aparently for it to apply
    adb reboot
    echo "Rebooting..."

    # Wait for it to reappear
    adb wait-for-device
    echo "Waiting for the device to respond"

    # Wait for the services to initialize
    sleep 20
}

change_secondary_display_behaviour()
{
    # Change secondary display behaviour
    adb shell pm grant com.farmerbb.taskbar android.permission.WRITE_SECURE_SETTINGS
    adb shell settings put global force_resizable_activities 1
    adb shell settings put global enable_freeform_support 1
    # adb shell settings put global enable_sizecompat_freeform 1
}

enable_screen()
{
    # Use the secondary screen option to generate the other screen
    # default: adb shell wm size ; adb shell wm density 
    # 1440x3200 450
    # 1080x2400 420 
    screen_size=2400x1440
    screen_density=210
    adb shell settings put global overlay_display_devices $screen_size/$screen_density
    sleep 1
    display=$(get_display)
    [[ $display ]] && adb shell "wm size $screen_size -d $display ; wm density $screen_density -d $display"  
    adb shell am start --display $display -n com.farmerbb.taskbar/.activity.SecondaryHomeActivity --windowingMode 1
}

disable_screen()
{
    # Disable the secondary screen option
    adb shell settings put global overlay_display_devices none
}

list_screen()
{
    # Get the display list
    adb shell dumpsys display | grep "  Display " | cut -d' ' -f4 | grep -v "0:" | sed -e 's/://'
}

launch_app()
{
    # adb shell dumpsys package com.farmerbb.taskbar > temp/taskbar.txt
    # adb shell am start-activity --display $display com.android.chrome  com.sec.android.app.dexonpc
    # com.sec.android.app.launcher/.activities.LauncherActivity
    app=${1:-"com.sec.android.app.sbrowser"}
    adb shell am start-activity --display $display $app --windowingMode 1
}

connect_screen()
{
    [[ -n $1 ]] && _size="-m $1" || _size="-m 1920"
    (scrcpy --display $display --window-title 'DexOnLinux' --stay-awake $_size) &
}

set_secondscreen()
{
    adb shell pm grant com.farmerbb.taskbar android.permission.WRITE_SECURE_SETTINGS
    adb shell pm grant com.farmerbb.secondscreen.free android.permission.WRITE_SECURE_SETTINGS 
    # adb shell pm set-home-activity "com.farmerbb.taskbar/.activity.SecondaryHomeActivity"
}

function check_adb()
{
    if ! command -v adb &> /dev/null
    then
        echo "adb could not be found"
        exit 1
    fi
    if ! (adb devices | grep ".*device$"); then
        echo "There is no device!!"
        exit  1
    fi
}

function launch_app()
{
    adb shell am start -n $1
    echo "Launched app $1"
}

function old_run()
{
    if ! display=$(get_display); then
        echo "None"
        change_secondary_display_behaviour
        enable_screen
        display=$(get_display)
    else
        echo "Display: $display"
    fi

    [[ "$1" == "off" ]] && { disable_screen ; exit ; }
    [[ "$1" == "con" ]] && { connect_screen $2 ; launch_app ; exit ; }
    [[ "$1" == "app" ]] && { launch_app $2 ; exit ; }
    [[ "$1" == "add" ]] && { enable_screen ; display=$(get_display) ; exit ; }
    [[ "_$1" != "_" ]] && { display=$1 ; connect_screen ; exit ; }
}

function get_display() {
    local output
    output=$(scrcpy --list-displays)
    local last_display_id
    last_display_id=$(echo "$output" | grep --only-matching --regexp='--display-id=[0-9]\+' | awk -F= '{ if ($2 > 2) print $2 }' | tail -n 1)
    if [ -n "$last_display_id" ]; then
        echo $last_display_id
        return 0
    else
        return 1
    fi
}

function get_apps()
{
    output=$(scrcpy --list-apps)
    start_processing=0

    while IFS= read -r line; do
        line=$(echo "$line" | xargs)
        if [[ $line =~ ^[*-] ]]; then
            line=$(echo "$line" | sed 's/^[*]\s*/- /')
            words=($line)
            package=${words[-1]}
            name=$(echo "${words[@]:0:${#words[@]}-1}" | tr -d '*-/\n[:space:]' | xargs)
            [[ -n $name ]] && app_list[$name]=$package
        fi
    done <<< "$output"
}

function run()
{
    local package=$1
    # if display=$(get_vdisplay); then
    #     scrcpy --display-id=$display --stay-awake --keyboard=uhid --start-app=$package &>/dev/null & disown
    # else
        scrcpy --new-display=2560x1440/240 --stay-awake --keyboard=uhid --start-app=$package &>/dev/null & disown
    # fi
}

function get_package()
{
    local name=$1
    for key in "${!app_list[@]}"; do
        if [[ ${key,,} =~ ${name,,} ]]; then
            echo "${app_list[$key]}"
            return
        fi
    done
    echo "No package found for $name"
}

function adb_ssh()
{
    adb forward tcp:8022 tcp:8022 && adb forward tcp:8080 tcp:8080
    ssh localhost -p 8022
}

check_adb

if [[ -n $1 ]]; then
    declare -A app_list
    get_apps
    package=$(get_package $1)
    echo "Running $1 - $package"
fi

[[ -n $package ]] && run $package