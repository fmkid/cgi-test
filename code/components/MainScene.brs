' ============================================================
' INIT
' ============================================================

' Inicializa referencias de UI, mensajes y arranca la reproducción
sub Init()
    sleep(500)

    m.video     = m.top.findNode("Video")
    m.menuGroup = m.top.findNode("MenuGroup")
    m.menuBkg   = m.top.findNode("MenuBkg")
    m.menuList  = m.top.findNode("MenuList")

    ' Configurar estado inicial
    m.video.notificationInterval = 60
    m.fetching = false
    m.stopTimes = {}

    LoadVideoData()
    PlayVideo(LoadIndexFromRegistry())

    ' Configurar observadores
    m.menuList.observeField("itemSelected", "OnMenuItemSelected")
    m.video.observeField("state", "OnVideoStateChange")
    m.video.observeField("position", "OnVideoPosition")
end sub


' ============================================================
' PLAYBACK
' ============================================================

' Decide si hacer fetch o reproducir directamente según si la URL corresponde a Pluto
sub PlayVideo(index as Integer)
    if m.video = invalid or m.menuList = invalid then return
    m.index = index
    SaveIndexToRegistry(index)
    m.selectedContent = m.menuList.content.getChild(index)
    if m.selectedContent = invalid then return

    m.fetchPlay = true
    isPluto = Instr(0, m.selectedContent.url, m.top.plutoPrefix + m.selectedContent.programId + m.top.plutoSuffix) > 0
    if isPluto and SecsUntilProgramEnd(m.index) > 0
        UpdateNotificationInterval(m.stopTimes[m.index.ToStr()])
        OnlyPlayVideo(m.selectedContent.secondaryTitle)
    else if isPluto
        FetchChannelData(true)
    else
        OnlyPlayVideo(m.top.noInfoChannelMsg)
    end if
end sub

' Lanza el fetch de info del canal. Si play=true arranca el video, si no solo actualiza la info
sub FetchChannelData(play as Boolean)
    if m.selectedContent = invalid then return
    m.fetchPlay = play
    m.fetching = true
    start = CreateObject("roDateTime").ToISOString()
    fetcher = CreateObject("roSGNode", "FetchData")
    fetcher.url = m.top.baseUrl + m.selectedContent.programId + "?start=" + start + "&stop=" + start
    fetcher.control = "RUN"
    fetcher.observeField("response", "OnFetchChannelData")
end sub

' Callback del fetch: parsea el programa actual y arranca o refresca según m.fetchPlay
sub OnFetchChannelData(event as Object)
    resp = event.getData()

    secTitle = m.top.noInfoChannelMsg
    if resp <> invalid and type(resp) = "roAssociativeArray" and resp.DoesExist("timelines")
        stopTime = CreateObject("roDateTime")
        for each program in resp.timelines
            stopTime.FromISO8601String(program.stop)
            if SecsFromNow(stopTime.AsSeconds()) > 0 then exit for
        end for

        UpdateNotificationInterval(stopTime.AsSeconds())
        secTitle = FormatSecTitle(program)
    end if

    OnlyPlayVideo(secTitle)
    m.fetching = false
end sub

' Actualiza el secondaryTitle y reproduce si hubo cambio de canal o si el título cambió
sub OnlyPlayVideo(secTitle as String)
    if m.selectedContent.url = m.top.rickRollUrl then secTitle = GetRickRollErrorMsg()
    titleChanged = secTitle <> m.selectedContent.secondaryTitle
    if titleChanged then m.selectedContent.secondaryTitle = secTitle
    ? "Ends in:"; SecsUntilProgramEnd(m.index); "s |"; m.index + 1; " | "; m.selectedContent.secondaryTitle
    if m.fetchPlay or titleChanged
        m.video.content = m.selectedContent
        ToggleMenu(false)
        m.video.control = "play"
    end if
end sub

' Guarda el stopTime y ajusta el notificationInterval al tiempo restante del programa
sub UpdateNotificationInterval(stopTimeSecs as Integer)
    m.stopTimes[m.index.ToStr()] = stopTimeSecs
    secsLeft = SecsUntilProgramEnd(m.index)
    interval = 1
    if secsLeft > 1 then interval = secsLeft
    m.video.notificationInterval = interval
end sub

' Retorna los segundos restantes del programa. Negativo o 0 significa que ya terminó
function SecsUntilProgramEnd(index as Integer) as Integer
    if not m.stopTimes.DoesExist(index.ToStr()) then return 0
    return SecsFromNow(m.stopTimes[index.ToStr()])
end function

' Retorna los segundos restantes desde ahora hasta un timestamp dado
function SecsFromNow(timeSecs as Integer) as Integer
    now = CreateObject("roDateTime")
    return timeSecs - now.AsSeconds()
end function

' Verifica en cada tick si el programa actual terminó y dispara el fetch automático
sub OnVideoPosition(ignored as Object)
    if m.selectedContent = invalid then return
    if SecsUntilProgramEnd(m.index) <= 0 then FetchChannelData(false)
end sub

' Maneja cambios de estado del video: error redirige al rickroll, finished lo reinicia
sub OnVideoStateChange(event as Object)
    state = event.getData()
    if state = "error" and not m.selectedContent.url = m.top.rickRollUrl
        m.selectedContent.url = m.top.rickRollUrl
        m.selectedContent.titleSeason = "Stream unavailable"
        m.selectedContent.secondaryTitle = GetRickRollErrorMsg()
    else if state = "finished" and m.selectedContent.url = m.top.rickRollUrl
        m.video.control = "play"
    end if
end sub

' Retorna el mensaje de error del rickroll según si hay uno o varios canales disponibles
function GetRickRollErrorMsg() as String
    if m.count > 1 then return m.top.rickRollMsg2
    return m.top.rickRollMsg1
end function


' ============================================================
' UI / NAVIGATION
' ============================================================

' Maneja eventos del control remoto: back alterna menú, up/down cambian canal
sub onKeyEvent(key as String, press as Boolean) as Boolean
    if press and m.count > 1 and not m.fetching
        if key = "back"
            ToggleMenu(not m.menuGroup.visible)
        else if (key = "up" or key = "down") and not m.menuGroup.visible
            PlayVideo(changeIndex(key))
        end if
    end if
    return m.count > 1
end sub

' Calcula el índice anterior o siguiente con wrap circular
function changeIndex(key as String) as Integer
    if key = "up" then return (m.count + m.index - 1) mod m.count
    if key = "down" then return (m.count + m.index + 1) mod m.count
end function

' Reproduce el canal seleccionado o cierra el menú si ya estaba seleccionado
sub OnMenuItemSelected(event as Object)
    index = event.getData()
    if index <> m.index
        PlayVideo(index)
    else
        ToggleMenu(false)
    end if
end sub

' Alterna la visibilidad del menú y transfiere el foco al elemento correspondiente
sub ToggleMenu(opt as Boolean)
    m.menuGroup.visible = opt
    if opt
        m.menuList.jumpToItem = m.index
        m.menuList.SetFocus(true)
    else
        m.video.SetFocus(true)
    end if
end sub


' ============================================================
' DATA
' ============================================================

' Obtiene la lista de canales desde FetchList y construye el ContentNode del menú
sub LoadVideoData()
    fetcher = CreateObject("roSGNode", "FetchList")
    response = validateResp(fetcher.response)

    m.count = 0
    content = CreateObject("roSGNode", "ContentNode")
    for each video in response
        if video.DoesExist("name") and video.name <> "" and video.DoesExist("_id")
            m.count++
            item = content.createChild("ContentNode")
            item.programId = video._id
            item.url = checkUrl(video._id, video.token)
            if response.count() > 1 then item.title = m.count.toStr() + ". "
            item.title += video.name
            if video.DoesExist("region") and video.region <> invalid and video.region <> "" then item.title += " [" + video.region + "]"
        end if
    end for

    if m.count > 1 and m.count < 13 then m.menuBkg.height = 75 * m.count + 45
    m.menuList.content = content
end sub

' Valida que la respuesta sea un array de objetos con name e _id. Retorna un item dummy si no es válida
function validateResp(resp as Object) as Object
    if resp <> invalid and type(resp) = "roArray" and resp.Count() > 0 and type(resp[0]) = "roAssociativeArray" and resp[0].DoesExist("name") and resp[0].DoesExist("_id") then return resp
    return [{"_id":"", "name": "Content not found"}]
end function

' Retorna la URL del video. Si está vacía usa rickRoll, si es un ID de Pluto construye la URL completa
function checkUrl(url as String, token as Object) as String
    if url = invalid or url = "" then return m.top.rickRollUrl
    if StrToI(url) > 0 then return m.top.plutoPrefix + url + m.top.plutoSuffix + token
    return url
end function


' ============================================================
' REGISTRY
' ============================================================

' Persiste el índice del canal actual en el registro del dispositivo
sub SaveIndexToRegistry(index as Integer)
    section = CreateObject("roRegistrySection", "cache")
    section.Write("stored_index", index.ToStr())
    section.Flush()
end sub

' Recupera el último índice guardado. Retorna 0 si no existe o está fuera de rango
function LoadIndexFromRegistry() as Integer
    section = CreateObject("roRegistrySection", "cache")
    data = section.Read("stored_index")
    if data <> invalid and data.Len() > 0
        index = StrToI(data)
        if index < m.count then return index
    end if
    return 0
end function


' ============================================================
' UTILS
' ============================================================

' Reemplaza todas las ocurrencias de find por replacement en original
function ReplaceString(original as String, find as String, replacement as String) as String
    parts = original.Split(find)
    result = ""
    for i = 0 to parts.Count() - 1
        if i = 0
            result = parts[i]
        else
            result = result + replacement + parts[i]
        end if
    end for
    return result
end function

' Retorna la posición de str2 dentro de str1 ignorando mayúsculas, espacios y tildes. 0 si no se encuentra
function CompareString(str1 as String, str2 as String) as Integer
    return Instr(0, SanitizeString(str1), SanitizeString(str2))
end function

' Normaliza un string a minúsculas, sin espacios ni tildes para comparación
function SanitizeString(str as String) as String
    str = LCase(str)
    str = ReplaceString(str, " ", "")
    str = ReplaceString(str, Chr(225), "a")
    str = ReplaceString(str, Chr(233), "e")
    str = ReplaceString(str, Chr(237), "i")
    str = ReplaceString(str, Chr(243), "o")
    str = ReplaceString(str, Chr(250), "u")
    return str
end function

' Construye el string de info del programa evitando duplicar título y nombre de episodio
function FormatSecTitle(program as Object) as String
    title    = program.title
    episode  = program.episode
    separator = ": "
    if CompareString(episode.name, title) > 0 then title = episode.name
    secondaryTitle = title
    if Instr(0, secondaryTitle, ":") > 0 then separator = " - "
    if CompareString(title, episode.name) = 0 then secondaryTitle += separator + episode.name
    secondaryTitle = ReplaceString(secondaryTitle, "(", "- ")
    secondaryTitle = ReplaceString(secondaryTitle, ")", "")
    secondaryTitle = ReplaceString(secondaryTitle, " /", " -")
    secondaryTitle = ReplaceString(secondaryTitle, "/ ", " - ")
    secondaryTitle = ReplaceString(secondaryTitle, "--", "-")
    secondaryTitle += " ("
    if episode.series.type = "film" then secondaryTitle += "Movie / "
    secondaryTitle += episode.genre + ")"
    return secondaryTitle
end function