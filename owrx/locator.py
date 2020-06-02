class Locator(object):
    @staticmethod
    def fromCoordinates(coordinates, depth=3):

        lat = coordinates["lat"]
        lon = coordinates["lon"]

        lon = lon + 180
        lat = lat + 90

        res = ""
        res += chr(65 + int(lon / 20))
        res += chr(65 + int(lat / 10))
        if depth >= 2:
            lon = lon % 20
            lat = lat % 10
            res += str(int(lon / 2))
            res += str(int(lat))
        if depth >= 3:
            lon = lon % 2
            lat = lat % 1
            res += chr(97 + int(lon * 12))
            res += chr(97 + int(lat * 24))

        return res
