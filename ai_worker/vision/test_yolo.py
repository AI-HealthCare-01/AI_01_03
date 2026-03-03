from ai_worker.vision.detector import predict_boxes

def main():
    out = predict_boxes("bus.jpg", conf_thres=0.5)
    print("BOXES_COUNT:", len(out))
    print(out)

if __name__ == "__main__":
    main()