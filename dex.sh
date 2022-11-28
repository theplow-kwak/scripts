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
    adb shell settings put global force_desktop_mode_on_external_displays 1
    adb shell settings put global force_resizable_activities 1
    adb shell settings put global enable_freeform_support 1
    adb shell settings put global enable_sizecompat_freeform 1
}

enable_screen()
{
    # Use the secondary screen option to generate the other screen
    # default: adb shell wm size ; adb shell wm density 
    # 1440x3200 450
    # 1080x2400 420 
    screen_size=2400x1440
    screen_density=240
    adb shell settings put global overlay_display_devices $screen_size/$screen_density
    sleep 1
    get_display
    [[ $display ]] && adb shell "wm size $screen_size -d $display ; wm density $screen_density -d $display"  
}

disable_screen()
{
    # Disable the secondary screen option
    adb shell settings put global overlay_display_devices none
    # adb shell settings delete global overlay_display_devices
}

list_screen()
{
    # Get the display list
    adb shell dumpsys display | grep "  Display " | cut -d' ' -f4 | grep -v "0:" | sed -e 's/://'
}

get_display()
{
    display=$(adb shell 'dumpsys display | grep mDisplayId= | cut -d "=" -f2 | sort -n | uniq | grep -v "^0$" | head -n1')
    if [[ $display ]]; then
        echo $display
        return 0
    else
        return 1
    fi
}

launch_app()
{
    # adb shell am start-activity --display $display com.android.chrome
    app=${1:-"com.sec.android.app.sbrowser"}
    adb shell am start-activity -S --display $display $app # --windowingMode 1 
}

connect_screen()
{
    (scrcpy --display $display --window-title 'DexOnLinux' --turn-screen-off --stay-awake) &
}

set_secondscreen()
{
    adb shell pm grant com.farmerbb.taskbar android.permission.WRITE_SECURE_SETTINGS
    adb shell pm grant com.farmerbb.secondscreen.free android.permission.WRITE_SECURE_SETTINGS    
}

if ! (adb devices | grep ".*device$"); then
    echo "There is no device!!"
    exit  1
fi

if ! display=$(get_display); then
    echo "None"
    enable_screen
    get_display
    change_secondary_display_behaviour
else
    echo "Display: $display"
fi

[[ "$1" == "off" ]] && { disable_screen ; exit ; }
[[ "$1" == "con" ]] && { connect_screen ; launch_app $2 ; exit ; }
[[ "$1" == "app" ]] && { launch_app $2 ; exit ; }
[[ "_$1" != "_" ]] && { display=$1 ; connect_screen $1 ; exit ; }

# com.sec.android.app.dexonpc
