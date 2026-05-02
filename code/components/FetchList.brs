sub init()
    m.top.response = GetDataFromLists()
end sub

function GetDataFromLists() as Object
    m.port = CreateObject("roMessagePort")
    m.urlXfer = CreateObject("roUrlTransfer")
    respList = CreateObject("roArray", 0, true)

    fetchedList = fetchJson(m.top.urlList)
    if fetchedList = invalid then return invalid

    listStart = fetchedList.listStart
    listEnd = fetchedList.listEnd
    listUrl = fetchedList.urlList
    max = listUrl.Count() - 1
    
    if listStart < 0 then listStart = 0
    if listEnd > max then listEnd = max

    token = fetchJson(m.top.tokenUrl)
    for i = listStart to listEnd
        response = fetchJson(listUrl[i].url)
        if type(response) = "roArray" and response.Count() > 0
            for each item in response
               item.region = listUrl[i].region
               if token.DoesExist("sessionToken") then item.token = token.sessionToken
               respList.push(item)
            end for
        end if
    end for
    return respList
 end function

function fetchJson(url as String) as Object
    m.urlXfer.SetCertificatesFile("common:/certs/ca-bundle.crt")
    m.urlXfer.InitClientCertificates()
    m.urlXfer.SetPort(m.port)

    if m.urlXfer = invalid or not m.urlXfer.SetUrl(url) or not m.urlXfer.AsyncGetToString()
        ? "[FetchData] Error al iniciar conexión"
        return {}
    end if

    while true
        msg = wait(0, m.port)
        if type(msg) = "roUrlEvent"
            if msg.GetResponseCode() = 200
                return ParseJson(msg.GetString())
            else
                ? "[FetchData] HTTP "; msg.GetResponseCode()
            end if
            exit while
        end if
    end while
    return {}
end function
