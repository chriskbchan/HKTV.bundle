# HKTV Plex Plugin
# Written by chriskbchan

import uuid, re

# Global
PREFIX = '/video/hktv'
NAME = 'HKTV'
ART = 'art-default.png'
ICON = 'icon-default.png'

UTF8 = 'utf-8'
FEA_zh = '精選點播節目'
VOD_zh = '全部點播節目'

cacheTime = float(Prefs['cachesec'])

# URLs
loginURL = 'https://www.hktvmall.com/hktv/zh/j_spring_security_check'
tokenURL = 'http://www.hktvmall.com/ott/token'
fListURL = 'http://ott-www.hktvmall.com/api/lists/getFeature'
pListURL = 'http://ott-www.hktvmall.com/api/lists/getProgram'
plReqURL = 'http://ott-www.hktvmall.com/api/playlist/request'
vInfoURL = 'http://ott-www.hktvmall.com/api/video/details'
mListURL = 'http://ott-www.hktvmall.com/api/preroll/getList'


# Start

def Start():
    ObjectContainer.title1 = NAME
    ObjectContainer.art = R(ART)
    DirectoryObject.thumb = R(ICON)

    Log('Start HKTV Plugin')

    Dict['UDID'] = str(uuid.uuid1())
    if 'uid' in Dict:
        if Dict['uid'] == '1' or not Dict['uid']:
            Log('Login HKTV...')
            Login(Prefs['username'], Prefs['password'])
    token = GetToken()
    if token:
        Dict['uid']  = token['user_id']
        Dict['muid'] = token['mallUid']
        Dict['tok']  = token['token']
        Dict['expy'] = token['expiry_date']
        Log('User ID: %s' % Dict['uid'])
    else:
        eMsg = 'Failed to get token'
        Log(eMsg)
        return MessageContainer(header=NAME, message=eMsg)

# Menu

@handler(PREFIX, NAME)
def MainMenu():

    oc = ObjectContainer(no_cache=True)

    HTTP.CacheTime = cacheTime
    #Log('Cache = %f sec' % cacheTime)

    Log('Main Menu')
    fJson = GetFeatureList()
    #Log('fJson: %s=%s' % (f, fJson[f]))

    # Live
    if Prefs['show_live']:
        if 'promo_video' in fJson:
            oc.add(GetLiveVideo(liveInfo=fJson['promo_video']))

    # Featured
    if Prefs['show_feature']:
        oc.add(DirectoryObject(key = Callback(FeatureMainMenu, fJson=fJson), title = FEA_zh.decode(UTF8)))

    # Program
    if Prefs['show_program']:
        oc.add(DirectoryObject(key = Callback(VODMainMenu), title = VOD_zh.decode(UTF8)))
  
    # Preferences
    #oc.add(PrefsObject(title='Settings'))

    return oc

# Live

@route(PREFIX, NAME + '/livevideo')
def GetLiveVideo(liveInfo, include_oc=False):
    vid       = liveInfo['video_id']
    title     = liveInfo['title']
    thumbnail = liveInfo['thumbnail']

    Log('Live Video - %s' % vid)

    vco = VideoClipObject(
        key = Callback(GetLiveVideo, liveInfo=liveInfo, include_oc=True),
        rating_key = NAME+vid,
        title = title.replace('HKTV ', ''),
        thumb = thumbnail,
        art = thumbnail,
        duration = 0,
        items = [ MediaObject(
            parts = [
                PartObject(key = HTTPLiveStreamURL(Callback(PlayVideo, vid=vid)))
            ]
        )]
    )

    if include_oc:
        oc = ObjectContainer()
        oc.add(vco)
        return oc
    else:
        return vco

# Feature

@indirect
@route(PREFIX, NAME + '/featured')
def FeatureMainMenu(fJson):
    Log('Feature Main Menu')
    # list all featured shows into directory objects

    oc = ObjectContainer(title2=FEA_zh.decode(UTF8))

    if 'videos' in fJson:
        dJson = fJson['videos']
        for p in range(len(dJson)):
            progInfo = dJson[p]
            if 'child_nodes' in progInfo:
                pvid      = progInfo['video_id']
                title     = progInfo['title']
                thumbnail = progInfo['thumbnail']
                summary   = GetSummary(pvid)
                oc.add(DirectoryObject(
                    key = Callback(VideoMenu, pvid=pvid, pTitle=title, pChilds=progInfo['child_nodes']),
                    title = title,
                    thumb = thumbnail,
                    art = thumbnail,
                    summary = summary
                ))

    return oc

# VOD

@indirect
@route(PREFIX, NAME + '/vod')
def VODMainMenu():
    Log('VOD Main Menu')
    # list all VOD programs into directory objects

    oc = ObjectContainer(title2=VOD_zh.decode(UTF8))

    aJson = GetProgramList()
    if 'videos' in aJson:
        pJson = aJson['videos']
        for p in range(len(pJson)):
            progInfo = pJson[p]
            if 'child_nodes' in progInfo:
                pgid      = progInfo['video_id']
                title     = progInfo['title']
                thumbnail = progInfo['thumbnail']
                summary   = GetSummary(pgid)
                oc.add(DirectoryObject(
                    key = Callback(VODProgMenu, pgid=pgid, pgTitle=title, pgChilds=progInfo['child_nodes']),
                    title = title,
                    thumb = thumbnail,
                    art = thumbnail,
                    summary = summary
                ))

    return oc

@indirect
@route(PREFIX, NAME + '/vodp/{pgid}/{pgTitle}/{pgChilds}')
def VODProgMenu(pgid, pgTitle, pgChilds):
    Log('VOD Program Menu - %s' % pgid)
    # list all episodes of a selected program into directory objects

    oc = ObjectContainer(title2=pgTitle)

    for e in range(len(pgChilds)):
        epiInfo = pgChilds[e]
        if 'child_nodes' in epiInfo:
            pvid      = epiInfo['video_id']
            title     = epiInfo['title']
            thumbnail = epiInfo['thumbnail']
            summary   = GetSummary(pvid)
            oc.add(DirectoryObject(
                    key = Callback(VideoMenu, pvid=pvid, pTitle=title, pChilds=epiInfo['child_nodes']),
                    title = title,
                    thumb = thumbnail,
                    art = thumbnail,
                    summary = summary
            ))

    return oc

@indirect
@route(PREFIX, NAME + '/videomenu/{pvid}/{pTitle}/{pChilds}')
def VideoMenu(pvid, pTitle, pChilds):
    Log('Video Menu - Parent VID - %s' % pvid)
    # list all videos of a selected show (parent) into directory objects (per section)

    oc = ObjectContainer(title2=pTitle)

    for i in range(len(pChilds)):
        oc.add(GetVideos(pvid=pvid, pTitle=pTitle, itemInfo=pChilds[i]))

    return oc

@route(PREFIX, NAME + '/video/{pvid}/{pTitle}/{itemInfo}')
def GetVideos(pvid, pTitle, itemInfo, include_oc=False):
    category  = itemInfo['category']
    vid       = itemInfo['video_id']
    title     = itemInfo['title']
    thumbnail = itemInfo['thumbnail']

    Log('Video Items - Parent VID - %s' % pvid)

    videos = []
    item_duration = 0
    pList = GetVideoPlaylist(vid)
    # insert ads
    if 'ads_cat' in pList:
        if len(pList['ads_cat']) > 0:
            adInfo = GetAds(vid, pList['ads_cat'], title, category, pList['m3u8_token'])
            #Log('adInfo=%s' % adInfo)
            for ad in range(len(adInfo)):
                ads_duration = int(adInfo[ad]['dur']) * 1000
                item_duration += ads_duration
                videos.append(
                    #PartObject(key = adInfo[ad]['media'],
                    PartObject(key = Callback(PlayVideo, url=adInfo[ad]['media'], dur=adInfo[ad]['dur'],
                                              imList=adInfo[ad]['imp'], tkList=adInfo[ad]['track']),
                               container = 'mp4',
                               duration = ads_duration)
                )
                Log('Parent ID - %s : added Ads ID %s' % (pvid, adInfo[ad]['id']))
    # insert video
    if 'm3u8' in pList:
        playURL = pList['m3u8']
        m3u8_duration = int(itemInfo['duration']) * 1000
        item_duration += m3u8_duration
        videos.append(
            PartObject(key = HTTPLiveStreamURL(Callback(PlayVideo, url=playURL)),
                       container = 'hls',
                       duration = m3u8_duration)
        )
        Log('Parent ID - %s : added VID %s' % (pvid, vid))

    vco = VideoClipObject(
        key = Callback(GetVideos, pvid=pvid, pTitle=pTitle, itemInfo=itemInfo, include_oc=True),
        rating_key = NAME+vid,
        title = title,
        thumb = thumbnail,
        art = thumbnail,
        duration = item_duration,
        items = [ MediaObject(
            parts = videos,
            container = 'hls'
            #duration = item_duration
        )]
    )

    if include_oc:
        oc = ObjectContainer()
        oc.add(vco)
        return oc
    else:
        return vco

@route(PREFIX, NAME + '/playvideo')
def PlayVideo(vid=None, url=None, dur=0, imList=None, tkList=None):
    playURL = ''
    if url:
        playURL = url
    elif vid:
        pList = GetVideoPlaylist(vid)
        if 'm3u8' in pList:
            playURL = pList['m3u8']
    Log('PlayVideo: %s' % playURL)
    # Ad tracking
    if dur > 0 and imList and tkList:
        Thread.Create(AdTrack, timer=dur, imList=imList, tkList=tkList)
    return Redirect(playURL)

# API

def Login(username, password):
    Log('User length: %d' % len(username))
    Log('Pass length: %d' % len(password))
    payload = { 'j_username' : username, 'j_password' : password  }
    try:
        resp = HTTP.Request(loginURL, values=payload, cacheTime=0.0, timeout=10.0)
        #Log('Login=%s' % resp)
        return True
    except Exception as e:
        Log('Login Err=%s' % e)
        return False

def GetToken():
    try:
        token = JSON.ObjectFromURL(tokenURL, cacheTime=0.0, timeout=10.0)
        #Log('Token=%s' % token)
        return token
    except Exception as e:
        Log('Token Err=%s' % e)
        return None

def GetFeatureList():
    #payload = { 'lim' : Prefs['maxvideos'], 'ofs' : '0' }
    url = '%s?lim=%s&ofs=%s' % (fListURL, Prefs['maxvideos'], '0')
    try:
        fList = JSON.ObjectFromURL(url, timeout=10.0)
        #Log('Featured=%s' % fList)
        return fList
    except Exception as e:
        Log('Featured Err=%s' % e)
        return {}

def GetProgramList():
    #payload = { 'lim' : Prefs['maxvideos'], 'ofs' : '0' }
    url = '%s?lim=%s&ofs=%s' % (pListURL, Prefs['maxvideos'], '0')
    try:
        pList = JSON.ObjectFromURL(url, timeout=10.0)
        #Log('Program=%s' % pList)
        return pList
    except Exception as e:
        Log('Program Err=%s' % e)
        return {}

def GetVideoPlaylist(vid):
    payload = { 'uid'  : Dict['uid'], 'vid'  : vid, 'udid' : Dict['UDID'], 't'    : Dict['tok'],
                'ppos' : '0',         '_'    : Dict['expy'] }
    try:
        playlist = JSON.ObjectFromURL(plReqURL, values=payload, timeout=10.0)
        Log('Playlist=%s' % playlist)
    except Exception as e:
        playlist = {}
        Log('GetVideoPlaylist Err=%s' % e)
    return playlist

def GetVideoDetail(vid):
    #payload = { 'vid' : vid }
    url = '%s?vid=%s' % (vInfoURL, vid)
    try:
        vData = JSON.ObjectFromURL(url, cacheTime=CACHE_1MONTH, timeout=5.0)
        #Log('vData=%s' % vData)
    except Exception as e:
        vData = {}
        Log('GetVideoDetail Err=%s' % e)
    return vData

def GetSummary(vid):
    summary = ''
    if Prefs['get_plot']:
        try:
            pMeta = GetVideoDetail(vid)
            #Log('pMeta=%s' % pMeta)
            if 'synopsis' in pMeta:
                summary = re.sub('(<br/>)+', ' ', pMeta['synopsis'])
        except Exception as e:
            Log('Unable to retrieve program details: err=%s' % e)
    return summary

def GetAds(vid, ads_cat, vn, vt, mtok):
    Log('Get Ads')

    try:
        ads_list = ','.join(ads_cat)
        ads_list = ads_list.join(['{','}'])
        payload = { 'muid' : Dict['muid'],
                    'uid'  : Dict['uid'],
                    'rt'   : 'WEB',
                    'ec'   : ads_list,
                    't'    : mtok,
                    'vid'  : vid,
                    'vn'   : vn,
                    'vt'   : vt  }
        url = '%s?%s' % (mListURL, '&'.join(['%s=%s' % (key, value) for (key, value) in payload.items()]))
        mXML = XML.ElementFromURL(url, cacheTime=0.0, timeout=5.0)
        #Log('Ads mXML=%s' % XML.StringFromElement(mXML))
        ads = ParseAds(mXML)
        return ads
    except Exception as e:
        ads = []
        Log('GetAds Err=%s' % e)
        return ads

def ParseAds(tree):
    ads = []
    try:
        for Ad in tree.findall('.//Ad'):
            id = int(Ad.get('id'))
            seq = int(Ad.get('sequence'))
            idx = seq - 1
            ads.append( {'id' : id, 'seq' : seq} )

            imList = []
            for Imp in Ad.findall('.//Impression'):
                url = str.strip(Imp.text)
                if url:
                    imList.append(url)
            ads[idx]['imp'] = imList

            for Dur in Ad.findall('.//Duration'):
                #st = time.strptime(str.strip(Dur.text), '%H:%M:%S')
                #totalSec = st.tm_min * 60 + st.tm_sec
                st = Datetime.TimestampFromDatetime(Datetime.ParseDate('1970-01-01 '+ str.strip(Dur.text)))
                totalSec = int(st) + 28800
            ads[idx]['dur'] = totalSec
        
            for Media in Ad.findall('.//MediaFile'):
                url = str.strip(Media.text)
            ads[idx]['media'] = url
        
            tkList = [ [], [] ]
            tkNext = 0
            for Track in Ad.findall('.//Tracking'):
                url = str.strip(Track.text)
                tkList[tkNext].append(url)
                tkNext = (tkNext + 1) % 2
            ads[idx]['track'] = tkList

    except Exception as e:
        Log('ParseAds Err=%s' % e)

    return ads

# Tracking

def GoURL(url):
    try:
        HTTP.Request(url, cacheTime=0.0, timeout=5.0)
    except Exception as e:
        Log('GoURL Err=%s' % e)
    return

def AdTrack(timer, imList, tkList):
    # impression
    for i in range(len(imList)):
        Log('Impression=%s' % imList[i])
        GoURL(imList[i])

    # tracking
    Log('Tracking started ...')
    sCount = 0
    intv = [ 0, timer / 4, timer / 2, timer / 4 * 3, timer ]
    t_tkList = map(list, zip(*tkList))

    while sCount <= timer:
        for i in range(len(intv)):
            interval = int(intv[i])
            if sCount == interval:
                for t in range(len(t_tkList[i])):
                    Log('Track - %d=%s' % (i, t_tkList[i][t]))
                    GoURL(t_tkList[i][t])
        sCount += 1
        if sCount < timer:
            Thread.Sleep(1.0)

    Log('Tracking completed ...')

#
