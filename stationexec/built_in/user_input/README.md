# User Input Tool
Provides Operations the ability to query the user for input.

## Station Tool Manifest Entry
```
{
    "tool_type": "user_input",
    "name": "User Input",
    "tool_id": "user_input",
    "configurations": {}
}
```

## Station Operation Usage
In a station's `Operation` class:

1. Require the user_input tool (`@require_tools("user_input")`)
2. Specify an input configuration dictionary
3. Pass the configuration dictionary to `self.user_input.get_input(<<input configuration>>)`
4. The returned value from `self.user_input.get_input` contains the user input results

**Example input configuration dictionary:**
```
input_data = {
    "check_1": {
        "type": "checkbox",
        "label": "Check the Box",
        "default": True
    },
    "check_2": {
        "type": "checkbox",
        "label": "Check the Box"
    },
    "radio_1": {
        "type": "radio",
        "label": "Choose One",
        "choices": ["Choice A", "Choice B"]
    },
    "text_1": {
        "type": "text",
        "label": "Type Here",
    },
    "dropdown_1": {
        "type": "dropdown",
        "choices": ["A", "B", "C", "D", "E"],
        "label": "Select One",
    },
    "message": "Operation One"
}
```

## Input Configuration

### Text
Textbox for string input.

#### Specification
```
{
    "type": "text",
    "label": <<String>>
}
```

### Checkbox
Checkbox for boolean (true/false) input. Provides an optional default value.

#### Specification
```
{
    "type": "checkbox",
    "label": <<String>>,
    "default": <<Optional, True/False>>
}
```

### Radio Buttons
List of buttons of which the user can select one.

#### Specification
```
{
    "type": "radio",
    "label": <<String>>,
    "choices": <<List of Strings>>
}
```

### Dropdown
Dropdown list of multiple values, user selects one.

#### Specification
```
{
    "type": "dropdown",
    "choices": <<List of Strings>>,
    "label": <<String>>,
}
```

### Message
Message string which renders at the top of the input window.

Any HTML injected into the string will be rendered in the UI:

"message": "\<h1>1.Do this\</h1>\<br>\<b>2.Now do that\</b>\<br>\<p>3.And you are done\</p>"

#### Specification
```
"message": <<String>>
```

## Release Notes
### V1.1
- UUID in input schema
- Handle message-only input windows
### V1.0
- Initial release
