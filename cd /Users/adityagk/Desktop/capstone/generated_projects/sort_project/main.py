from sorter import merge_sort

def main():
    sample_data = [38, 27, 43, 3, 9, 82, 10]
    print(f"Original array: {sample_data}")
    
    sorted_data = merge_sort(sample_data)
    print(f"Sorted array: {sorted_data}")

if __name__ == "__main__":
    main()
