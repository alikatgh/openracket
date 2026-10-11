on run argv
  display alert "OpenRacket could not start" message (item 1 of argv) as critical buttons {"OK"} default button "OK"
end run
