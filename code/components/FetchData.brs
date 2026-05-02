sub init()
    m.top.functionName = "fetchData"
end sub

sub fetchData()
    m.port = CreateObject("roMessagePort")
    m.urlXfer = CreateObject("roUrlTransfer")
    m.top.response = fetchJson(m.top.url)
end sub

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