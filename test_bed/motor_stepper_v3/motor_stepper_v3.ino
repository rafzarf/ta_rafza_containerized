// Define the pins connected to the limit switches
const int limitSwitchPin1 = 18; // GPIO pin 18
const int limitSwitchPin2 = 19; // GPIO pin 23

// Define stepper motor connections and steps per revolution
#define dirPin 2
#define stepPin 4
#define stepsPerRevolution 800  // Change this to match 800 steps per revolution

int stepDelay = 400;  // Step delay for faster movement (in microseconds)
bool motorRunning = false;  // To track whether the motor is running
bool autoControl = false;   // To track if limit switches are controlling the motor
unsigned long lastStepTime = 0;  // To track the timing of each step

unsigned long debounceDelay = 50; // Debounce delay in milliseconds4as
unsigned long switch1LastPressTime = 0;
unsigned long switch2LastPressTime = 0;
unsigned long switch1PressedDuration = 0;
unsigned long switch2PressedDuration = 0;

// Debounced states for limit switches
bool switch1DebouncedState = HIGH;
bool switch2DebouncedState = HIGH;

void setup() {
  // Declare pins as output:
  pinMode(stepPin, OUTPUT);
  pinMode(dirPin, OUTPUT);

  // Configure the limit switch pins as input with pull-up resistors
  pinMode(limitSwitchPin1, INPUT_PULLUP);
  pinMode(limitSwitchPin2, INPUT_PULLUP);
  
  // Initialize serial communication at 9600 bits per second:
  Serial.begin(9600);

  // Print instructions to serial monitor
  Serial.println("Enter commands to control the stepper motor:");
  Serial.println("f: move forward");
  Serial.println("b: move backward");
  Serial.println("1-9: adjust speed (1 is slow, 9 is fast)");
  Serial.println("s: stop motor");
}

void loop() {
  unsigned long currentTime = millis();

  // Debounce limit switch 1
  int currentSwitch1State = digitalRead(limitSwitchPin1);
  if (currentSwitch1State != switch1DebouncedState) {
    if (currentTime - switch1LastPressTime > debounceDelay) {
      switch1DebouncedState = currentSwitch1State;
      switch1LastPressTime = currentTime;

      // Handle switch 1 press
      if (switch1DebouncedState == LOW) {
        switch1PressedDuration = currentTime;
        Serial.println("Limit switch 1 pressed, moving forward automatically...");
        motorRunning = true;
        autoControl = true;
        digitalWrite(dirPin, HIGH);  // Set direction to forward
      }
    }
  } else if (switch1DebouncedState == LOW && (currentTime - switch1PressedDuration) > 5000) {
    // If the limit switch 1 has been held LOW for more than 5 seconds
    Serial.println("Fault detected: Limit switch 1 stuck.");
    motorRunning = false;  // Stop motor on fault
  }

  // Debounce limit switch 2
  int currentSwitch2State = digitalRead(limitSwitchPin2);
  if (currentSwitch2State != switch2DebouncedState) {
    if (currentTime - switch2LastPressTime > debounceDelay) {
      switch2DebouncedState = currentSwitch2State;
      switch2LastPressTime = currentTime;

      // Handle switch 2 press
      if (switch2DebouncedState == LOW) {
        switch2PressedDuration = currentTime;
        Serial.println("Limit switch 2 pressed, moving backward automatically...");
        motorRunning = true;
        autoControl = true;
        digitalWrite(dirPin, LOW);  // Set direction to backward
      }
    }
  } else if (switch2DebouncedState == LOW && (currentTime - switch2PressedDuration) > 5000) {
    // If the limit switch 2 has been held LOW for more than 5 seconds
    Serial.println("Fault detected: Limit switch 2 stuck.");
    motorRunning = false;  // Stop motor on fault
  }

  // Handle motor movement
  if (motorRunning) {
    unsigned long currentMicros = micros();
    if (currentMicros - lastStepTime >= stepDelay) {
      digitalWrite(stepPin, HIGH);
      delayMicroseconds(10); // Brief pulse
      digitalWrite(stepPin, LOW);
      lastStepTime = currentMicros;  // Update last step time
    }
  }

  // Handle manual control (Serial Commands)
  if (Serial.available() > 0) {
    char incomingByte = Serial.read();
    handleManualControl(incomingByte);
  }
}

// Function to handle manual control from the serial monitor
void handleManualControl(char incomingByte) {
  switch (incomingByte) {
    case 'f':
      Serial.println("Manual command: Moving forward...");
      motorRunning = true;
      autoControl = false;
      digitalWrite(dirPin, HIGH);  // Set direction to forward
      break;

    case 'b':
      Serial.println("Manual command: Moving backward...");
      motorRunning = true;
      autoControl = false;
      digitalWrite(dirPin, LOW);  // Set direction to backward
      break;

    case 's':
      Serial.println("Manual command: Stopping motor...");
      motorRunning = false;  // Stop the motor
      break;

    case '1' ... '9':  // Speed control (1 to 9)
      stepDelay = map(incomingByte - '0', 1, 9, 1000, 200);  // Map speed to delay range (lower = faster)
      Serial.print("Speed set to ");
      Serial.println(incomingByte - '0');
      break;

    default:
      Serial.println("Invalid command. Use 'f', 'b', 's', or '1-9' to control the motor.");
      break;
  }
}