import re
import json
import urllib.parse
import requests


class YoutubeSearch:
    def __init__(self, search_terms: str, max_results=None, yt_music=False, duration=None):
        self.search_terms = search_terms
        self.max_results = max_results
        self.yt_music = yt_music
        self.duration = duration
        self.retries = 0
        self.max_time_deviation = 10  # Settings Sekunden
        self.max_retries = 3             # Settings
        self.disable_mv_filter = False
        self.videos = self._search()


    def _search(self):
        encoded_search = urllib.parse.quote_plus(self.search_terms)
        url = f"https://www.youtube.com/results?search_query={encoded_search}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }

        response = requests.get(url, headers=headers).text

        match = re.search(r"ytInitialData\s*=\s*(\{.*?\});", response, re.S)
        if not match:
            raise ValueError("ytInitialData not found")


        results = self._parse_html(response)
        print("results:", results)
        # Wenn es keine Ergebnisse gab, und es noch nicht ohne den Filter versucht wurde,
        # versuche es erneut ohne den Filter
        if not results and not self.disable_mv_filter:
            self.retries = 0
            self.disable_mv_filter = True
            results = self._parse_html(response)

        if not results and self.disable_mv_filter:
            print("No results found")
            return []

        return results[: self.max_results]


    def _is_music_video(self, video_data):

        extended_filter = ["extended mix", "extended", "extended music mix"]
        mv_filter = ["official video", "music video", "official mv", "official hd video", "video clip", " mv", "official music video"]

        title = (
            video_data.get("title", {})
            .get("runs", [{}])[0]
            .get("text", "")
            .lower()
        )

        channel = (
            video_data.get("longBylineText", {})
            .get("runs", [{}])[0]
            .get("text", "")
            .lower()
        )

        print(self.search_terms, "  ", title, "filter_disabled: ", self.disable_mv_filter)

        # Topic-Videos sind idR. die beste Wahl
        if channel.endswith(" - topic"):
            return True

        # Wenn "extended" in der Suchanfrage steht
        if not any(word in self.search_terms for word in extended_filter):

            # Wenn "extended" in dem Ergebnis der Suchanfrage steht,
            # soll es rausgefiltert werden, da es nicht gewünscht ist
            if any(word in title for word in extended_filter):
                return False

        # Filter wird deaktiviert, wenn sonst keine Ergebnisse gefunden wurden
        if not self.disable_mv_filter:
            # Wenn "Music Video" in der Suchanfrage steht
            if not any(word in self.search_terms for word in mv_filter):

                if any(word in title for word in mv_filter):
                    return False

        print("Passendes Video: ", title)
        return True

    def _parse_html(self, response):
        results = []

        start = response.index("ytInitialData") + len("ytInitialData") + 3
        end = response.index("};", start) + 1
        json_str = response[start:end]
        data = json.loads(json_str)

        contents = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )

        for section in contents:
            items = (
                section.get("itemSectionRenderer", {})
                .get("contents", [])
            )

            for item in items:
                if "videoRenderer" not in item:
                    continue
                print(self.retries, "retries")
                video_data = item["videoRenderer"]

                # Nach zu vielen Versuchen wird der Suchvorgang abgebrochen, da es keine korrekten Ergebnisse gibt
                if self.retries >= self.max_retries:
                    return []

                self.retries += 1

                if self.yt_music and not self._is_music_video(video_data):
                    continue


                # Wenn eine Sekundenzahl gegeben ist, vergleiche die Länge mit dem Suchergebnis
                if self.duration:
                    yt_duration = video_data.get("lengthText", {}).get("simpleText")
                    split = yt_duration.split(":")

                    if len(split) == 2:
                        yt_duration = int(yt_duration.split(":")[0]) * 60 + int(yt_duration.split(":")[1])
                    elif len(split) == 3:
                        yt_duration = (int(yt_duration.split(":")[0]) * 3600 +
                                       int(yt_duration.split(":")[1]) * 60 +
                                       int(yt_duration.split(":")[2])
                                       )

                    diff = abs(yt_duration - self.duration)
                    print(yt_duration, self.duration, diff)

                    if diff > self.max_time_deviation:
                        print("Video duration does not match the given duration")
                        continue

                res = {
                    "id": video_data.get("videoId"),
                    "title": video_data.get("title", {})
                             .get("runs", [{}])[0]
                             .get("text") or "",
                    "channel": video_data.get("longBylineText", {})
                               .get("runs", [{}])[0]
                               .get("text") or "",
                    "duration": video_data.get("lengthText", {})
                    .get("simpleText"),
                    "views": video_data.get("viewCountText", {})
                    .get("simpleText"),
                    "publish_time": video_data.get("publishedTimeText", {})
                    .get("simpleText"),
                    "thumbnails": [
                        t.get("url") for t in
                        video_data.get("thumbnail", {})
                        .get("thumbnails", [])
                    ],
                    "url_suffix": video_data.get("navigationEndpoint", {})
                    .get("commandMetadata", {})
                    .get("webCommandMetadata", {})
                    .get("url"),
                }

                results.append(res)

                if self.max_results and len(results) >= self.max_results:
                    return results

        return results

    def __clear_cache__(self):
        self.videos = []
        self.retries = 0
        self.disable_mv_filter = False

    def to_dict(self, clear_cache=True):
        result = self.videos

        if clear_cache:
            self.__clear_cache__()
        return result

    def to_json(self, clear_cache=True):
        result = json.dumps({"videos": self.videos}, ensure_ascii=False)

        if clear_cache:
            self.__clear_cache__()
        return result
