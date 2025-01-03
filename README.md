# GainsGPT

GainsGPT is a workout log and exercise tracker powered by AI. It uses the Hugging Face Inference API to parse and extract structured data from your workout notes. This leaves you the freedom to write your workout logs in natural language and in your own preferred style, respecting minimal formatting guidelines, while AI takes care of the extraction and organization of the data.

## Features

- **Add Workout Logs**: Log your workout sessions with detailed notes.
- **Edit/Delete Logs**: Modify or remove existing workout logs.
- **Track Exercises**: View and track data for specific exercises.
- **Track Metrics**: Monitor daily metrics such as sleep quality, pain, and energy levels.

## Setup

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/GainsGPT.git
    cd GainsGPT
    ```

2. Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    ```

3. Set up your Hugging Face API token:
    ```sh
    export HF_TOKEN=your_hugging_face_api_token
    ```

4. Run the Streamlit app:
    ```sh
    streamlit run app.py
    ```

## Usage

- Navigate to the "Log" section to add a new workout log.
- Use the "Exercises" section to view and track specific exercises.
- Check the "Tracking" section to monitor daily metrics.

## License

This project is licensed under the MIT License.
