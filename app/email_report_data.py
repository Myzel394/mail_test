from dataclasses import dataclass, field

_all__ = [
    "EmailReportProxyImageData",
    "EmailReportSinglePixelImageTrackerData",
    "EmailReportData",
]


@dataclass
class EmailReportProxyImageData:
    url: str
    image_proxy_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "url": self.url,
            "image_proxy_id": self.image_proxy_id,
        }


@dataclass
class EmailReportSinglePixelImageTrackerData:
    source: str
    tracker_name: str
    tracker_url: str

    def as_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "tracker_name": self.tracker_name,
            "tracker_url": self.tracker_url,
        }


@dataclass
class EmailReportData:
    version = "1.0"
    mail_from: str
    mail_to: str
    proxied_images: list[EmailReportProxyImageData] = field(
        default_factory=lambda: []
    )
    single_pixel_images: list[EmailReportSinglePixelImageTrackerData] = field(
        default_factory=lambda: []
    )

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            "message_details": {
                "meta": {
                    "from": self.mail_from,
                    "to": self.mail_to,
                },
                "content": {
                    "proxied_images": [
                        image.as_dict()
                        for image in self.proxied_images
                    ],
                    "single_pixel_images": [
                        single_pixel_image.as_dict()
                        for single_pixel_image in self.single_pixel_images
                    ]
                }
            }
        }

