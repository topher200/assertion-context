import { Component } from '@angular/core';

@Component({
  selector: 'traceback-app',
  template: `
<header class="container">
  <h1>{{heading}}</h1>
</header>
<tracebacks></tracebacks>
`,
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  heading = "Tracebacks"
}
