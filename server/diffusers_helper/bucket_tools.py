"""
This module contains tools for working with pre-defined resolution "buckets".
Many modern generative models are trained on images of various aspect ratios,
but not arbitrary sizes. These aspect ratios are grouped into buckets. This
module helps find the most appropriate bucket for a given input image to
minimize cropping and distortion during preprocessing.
"""
bucket_options = {
    640: [
        (416, 960),
        (448, 864),
        (480, 832),
        (512, 768),
        (544, 704),
        (576, 672),
        (608, 640),
        (640, 608),
        (672, 576),
        (704, 544),
        (768, 512),
        (832, 480),
        (864, 448),
        (960, 416),
    ],
}


def find_nearest_bucket(h, w, resolution=640):
    """
    Finds the bucket with the aspect ratio closest to the input dimensions.

    The model was not trained on arbitrary resolutions but on a fixed set of
    height/width pairs (buckets) that maintain a similar total number of pixels.
    This function identifies the best bucket to use for a given input image
    to ensure the preprocessed image's aspect ratio is as close as possible
    to the original's, minimizing the amount of cropping required.

    Args:
        h (int): The height of the input image.
        w (int): The width of the input image.
        resolution (int): A key to select a group of pre-defined aspect ratio
                          buckets. For the current model, only 640 is supported.

    Returns:
        tuple[int, int]: The (height, width) of the best-matching bucket.
    """
    buckets = bucket_options.get(resolution)

    if not buckets:
        raise ValueError(f"No buckets are defined for the specified resolution key: {resolution}")

    min_metric = float('inf')
    best_bucket = None

    for (bucket_h, bucket_w) in buckets:
        # This metric calculates a value proportional to the difference in aspect ratios.
        # A smaller metric means a closer match.
        metric = abs(h * bucket_w - w * bucket_h)
        if metric < min_metric:
            min_metric = metric
            best_bucket = (bucket_h, bucket_w)

    if best_bucket is None:
        raise RuntimeError(f"Could not find a suitable bucket for resolution {resolution}. This is unexpected.")

    return best_bucket
