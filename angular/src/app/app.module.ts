import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpModule } from '@angular/http';

import { AppComponent } from './app.component';
import { TracebacksComponent } from './tracebacks/tracebacks.component';
import { RaceService } from './tracebacks/race.service';

@NgModule({
  declarations: [
    AppComponent,
    TracebacksComponent
  ],
  imports: [
    BrowserModule,
    FormsModule,
    HttpModule
  ],
  providers: [ RaceService ],
  bootstrap: [AppComponent]
})
export class AppModule { }
