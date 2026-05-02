' first thing that happens in a channel'
sub main()
  screen = CreateObject("roSGScreen")
  m.port = CreateObject("roMessagePort")
  screen.setMessagePort(m.port)
  screen.CreateScene("MainScene")
  screen.show()

  while(true)
    msg = wait(0, m.port)
    msgType = type(msg)
    if msgType = "roSGScreenEvent" and msg.isScreenClosed() then return
  end while
end sub
